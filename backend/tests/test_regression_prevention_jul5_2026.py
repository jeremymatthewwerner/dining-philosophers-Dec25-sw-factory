"""Regression-prevention tests (July 5, 2026 - Sunday QA).

Sunday's QA focus is guarding recent bug fixes so they cannot silently regress.

The most recent real bug fix is **#978**
``fix(thinker): centralize Anthropic model id, replace retired 404ing snapshot``.

Background: the dated snapshot ``claude-sonnet-4-20250514`` was retired by
Anthropic and started returning ``404 not_found_error`` from *every* thinker
suggestion / response / validation call. That broke ~9 E2E tests on any PR
running the E2E suite and silently killed the suggestion feature in production.
The fix replaced **5 hardcoded copies** of the model id in
``app/services/thinker.py`` with a single source of truth,
``settings.anthropic_model`` (see ``app/core/config.py``).

The shipped fix only added regression guards for **2 of the 5** call sites
(``validate_thinker`` in ``test_thinker_service.py`` and the config default in
``test_config.py``). This module closes that gap with:

1. Per-call-site guards proving that each of the remaining API call sites
   (``suggest_thinkers``, ``generate_response``, ``generate_user_prompt`` and the
   streaming ``generate_response_with_streaming_thinking``) forwards the
   *configured* model rather than a hardcoded id, and never the retired snapshot.
2. A **source-level** guard over ``app/`` that fails if a hardcoded dated model
   snapshot (``claude-...-YYYYMMDD``) is ever reintroduced anywhere, and that
   confirms every ``model=`` argument inside ``thinker.py`` is sourced from
   ``settings.anthropic_model``.

Together these ensure that if anyone re-hardcodes a model id at any of the call
sites - or a new call site - a fast unit test fails long before it reaches the
E2E suite or production.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import app.services.thinker as thinker_module
from app.models.message import SenderType
from app.services.thinker import ThinkerService
from tests.conftest import (
    create_mock_anthropic_response,
    create_mock_thinker_suggestion_json,
)

# The exact retired snapshot that caused #973/#978. It must never reappear as a
# hardcoded id anywhere in the application source or in an outgoing API call.
RETIRED_MODEL = "claude-sonnet-4-20250514"

# A sentinel model id used to prove the value flows from settings (not a literal).
SENTINEL_MODEL = "claude-regression-sentinel-xyz"


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


def _make_thinker() -> MagicMock:
    """Build a Message/prompt-builder-compatible thinker mock."""
    thinker = MagicMock()
    thinker.name = "Socrates"
    thinker.bio = "Classical philosopher"
    thinker.positions = "Question everything"
    thinker.style = "Dialectic"
    return thinker


def _service_with_sentinel_model(response_text: str) -> tuple[ThinkerService, AsyncMock]:
    """ThinkerService whose ``messages.create`` returns ``response_text``.

    The service's ``settings.anthropic_model`` is set to :data:`SENTINEL_MODEL`
    so tests can assert the outgoing call used the configured value.
    """
    service = ThinkerService()
    mock_response = create_mock_anthropic_response(response_text)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    service._client = mock_client
    service.settings.anthropic_model = SENTINEL_MODEL
    return service, mock_client


def _assert_used_sentinel_model(mock_client: AsyncMock) -> None:
    """Assert the non-streaming API call forwarded the configured model."""
    mock_client.messages.create.assert_awaited()
    used_model = mock_client.messages.create.call_args.kwargs["model"]
    assert used_model == SENTINEL_MODEL, (
        f"call site used {used_model!r} instead of the configured model"
    )
    assert used_model != RETIRED_MODEL


class TestModelCentralizationPerCallSite:
    """#978: every non-streaming call site must forward ``settings.anthropic_model``."""

    async def test_suggest_thinkers_uses_configured_model(self) -> None:
        """``suggest_thinkers`` forwards the configured model, not a hardcoded id.

        Regression guard for #978 - this call site (thinker.py ~315) was one of
        the four left unguarded by the original fix.
        """
        json_text = create_mock_thinker_suggestion_json(
            name="Socrates",
            reason="Master of questioning",
            bio="Ancient Greek philosopher",
            positions="Socratic method",
            style="Questions everything",
        )
        service, mock_client = _service_with_sentinel_model(json_text)

        await service.suggest_thinkers("philosophy", 1)

        _assert_used_sentinel_model(mock_client)

    async def test_generate_response_uses_configured_model(self) -> None:
        """``generate_response`` forwards the configured model (thinker.py ~1041)."""
        service, mock_client = _service_with_sentinel_model("I think therefore I am.")
        thinker = _make_thinker()
        message = MagicMock()
        message.sender_type = SenderType.USER
        message.sender_name = None
        message.content = "What is existence?"

        await service.generate_response(thinker, [message], "philosophy")

        _assert_used_sentinel_model(mock_client)

    async def test_generate_user_prompt_uses_configured_model(self) -> None:
        """``generate_user_prompt`` forwards the configured model (thinker.py ~1527)."""
        service, mock_client = _service_with_sentinel_model("Alice, what do you think?")
        thinker = _make_thinker()
        message = MagicMock()
        message.sender_type = SenderType.USER
        message.sender_name = "Alice"
        message.content = "What is truth?"

        await service.generate_user_prompt(thinker, [message], "philosophy", "Alice")

        _assert_used_sentinel_model(mock_client)


class TestModelCentralizationStreaming:
    """#978: the streaming call site must also forward ``settings.anthropic_model``."""

    async def test_streaming_response_uses_configured_model(self) -> None:
        """``generate_response_with_streaming_thinking`` forwards the configured model.

        The streaming path (thinker.py ~608) uses ``client.messages.stream`` rather
        than ``messages.create``; it was the fifth unguarded call site. We drive the
        method with a fake stream and assert the ``model`` kwarg handed to
        ``messages.stream`` came from ``settings.anthropic_model``.
        """

        class _FakeStream:
            async def __aenter__(self) -> _FakeStream:
                return self

            async def __aexit__(self, *exc: Any) -> None:
                return None

            def __aiter__(self) -> _FakeStream:
                self._done = True
                return self

            async def __anext__(self) -> MagicMock:
                raise StopAsyncIteration

            async def get_final_message(self) -> MagicMock:
                final = MagicMock()
                final.usage.input_tokens = 10
                final.usage.output_tokens = 5
                final.content = []
                return final

        stream_mock = MagicMock(return_value=_FakeStream())
        mock_client = MagicMock()
        mock_client.messages.stream = stream_mock

        service = ThinkerService()
        service._client = mock_client
        service.settings.anthropic_model = SENTINEL_MODEL
        thinker = _make_thinker()

        with patch("app.services.thinker.manager") as mock_manager:
            mock_manager.get_speed_multiplier.return_value = 1.0
            mock_manager.is_conversation_active.return_value = True
            mock_manager.send_thinker_typing = AsyncMock()
            mock_manager.send_thinker_stopped_typing = AsyncMock()
            mock_manager.send_thinker_thinking = AsyncMock()
            mock_manager.send_thinker_message = AsyncMock()
            mock_manager.broadcast_to_conversation = AsyncMock()

            await service.generate_response_with_streaming_thinking(
                "conv-1", thinker, [], "philosophy"
            )

        stream_mock.assert_called_once()
        used_model = stream_mock.call_args.kwargs["model"]
        assert used_model == SENTINEL_MODEL
        assert used_model != RETIRED_MODEL


class TestNoHardcodedModelInSource:
    """#978: source-level guards against re-hardcoding a dated model snapshot."""

    def _thinker_source(self) -> str:
        return Path(thinker_module.__file__).read_text(encoding="utf-8")

    def test_thinker_has_no_hardcoded_dated_snapshot(self) -> None:
        """No ``claude-...-YYYYMMDD`` literal may appear in ``thinker.py``.

        This is the exact class of bug from #978: a dated snapshot silently rots
        when Anthropic retires it. Matching the *pattern* (not just the one retired
        id) catches any future hardcoded snapshot too.
        """
        dated_snapshot = re.compile(r"claude-[a-z0-9.\-]*-\d{8}")
        matches = dated_snapshot.findall(self._thinker_source())
        assert matches == [], f"hardcoded dated model snapshot(s) in thinker.py: {matches}"

    def test_no_app_source_references_retired_model(self) -> None:
        """The specific retired snapshot must not appear anywhere in ``app/``.

        Belt-and-suspenders: even outside thinker.py, re-introducing the exact
        404ing id would re-break the feature.
        """
        app_dir = Path(thinker_module.__file__).resolve().parents[1]
        offenders = [
            str(path.relative_to(app_dir.parent))
            for path in app_dir.rglob("*.py")
            if RETIRED_MODEL in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], f"retired model id {RETIRED_MODEL!r} found in: {offenders}"

    def test_every_model_kwarg_in_thinker_uses_settings(self) -> None:
        """Every ``model=`` argument in ``thinker.py`` sources from settings.

        The fix centralized 5 call sites on ``self.settings.anthropic_model``.
        This guard fails if a call site is added or edited to pass a literal string
        (or any other expression) for ``model=`` instead of the shared config value.
        """
        source = self._thinker_source()
        model_kwargs = re.findall(r"\bmodel=([^,\n]+)", source)
        assert model_kwargs, "expected at least one model= argument in thinker.py"
        # All five known API call sites; keep the exact expected count so a new
        # call site forces an explicit review of this guard.
        assert len(model_kwargs) == 5, (
            f"expected 5 model= call sites in thinker.py, found {len(model_kwargs)}: {model_kwargs}"
        )
        for value in model_kwargs:
            assert value.strip() == "self.settings.anthropic_model", (
                f"model= argument is not centralized: {value.strip()!r}"
            )
