"""Regression prevention tests for Sunday QA (June 28, 2026).

Focus: pin down the behavioral and source-level invariants of the *freshest*
shipped fix that no earlier Sunday regression suite has had a chance to guard.

The newest merged ``fix(...)`` commit is #978 (commit 6860aa4, June 20 2026):

    fix(thinker): centralize Anthropic model id, replace retired 404ing snapshot

The hardcoded model ``claude-sonnet-4-20250514`` was retired by Anthropic and
began returning ``404 not_found_error`` from *every* thinker suggestion,
response, streaming and validation call -- breaking ~9 E2E tests and the
suggestion feature in production. The fix replaced **five** hardcoded copies of
the dated snapshot in ``thinker.py`` with a single source of truth:
``settings.anthropic_model`` (default ``claude-sonnet-4-6``, env-overridable).

The merged fix shipped two tests:
  * ``test_config``: the default model is a current alias, never the retired
    snapshot; it is overridable.
  * ``test_thinker_service``: ``validate_thinker`` passes the configured model.

That leaves a real regression gap. Only **one** of the five call sites
(``validate_thinker``) is behaviourally pinned, and *nothing* guards against a
future refactor silently re-introducing a hardcoded dated snapshot at any of
the other four call sites (``_suggest_single_batch``, the streaming-thinking
path, ``generate_response``, ``generate_user_prompt``). A reviewer-aid that
fails the moment a dated literal reappears -- or the moment a call site stops
reading ``settings.anthropic_model`` -- is exactly the "data quietly rots"
failure mode that black-box tests miss: the suggestion call would 404 only
against the live API, long after the green CI run.

This file closes that gap with three layers of guard:

- TestAnthropicModelConfigContract (4): the config field that is the single
  source of truth -- type, no-dated-snapshot default, env override.
- TestThinkerModelCentralizationSource (5): AST/source-level guards proving
  *every* Anthropic call in ``thinker.py`` reads ``self.settings.anthropic_model``
  and *no* dated snapshot literal survives anywhere in the module.
- TestThinkerModelCentralizationBehavioral (4): per-call-site behavioural
  proof that the configured model id actually reaches the API kwargs for the
  four call sites the merged fix never pinned.
"""

import ast
import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.models.message import SenderType
from app.services import thinker as thinker_module
from app.services.thinker import ThinkerService
from tests.conftest import (
    create_mock_anthropic_response,
    create_mock_thinker_suggestion_json,
)

# A dated Anthropic model snapshot looks like ``claude-<family>-<n>-YYYYMMDD``.
# The specific one that 404'd was ``claude-sonnet-4-20250514``; this pattern
# catches *any* 8-digit dated snapshot so a different rotted literal can't sneak
# back in under the radar.
_DATED_SNAPSHOT_RE = re.compile(r"claude-[a-z0-9.-]*\d{8}")
_RETIRED_SNAPSHOT = "claude-sonnet-4-20250514"

# Path to the module under guard, resolved from the imported module so the test
# follows the source wherever it lives.
_THINKER_SOURCE_PATH = Path(thinker_module.__file__)
_THINKER_SOURCE = _THINKER_SOURCE_PATH.read_text(encoding="utf-8")
_THINKER_TREE = ast.parse(_THINKER_SOURCE)


def _iter_anthropic_calls(tree: ast.AST) -> list[ast.Call]:
    """Return every ``*.messages.create(...)`` / ``*.messages.stream(...)`` call.

    These are the Anthropic API entry points that must each carry a centralized
    ``model=self.settings.anthropic_model`` keyword. Matching on the
    ``messages.create`` / ``messages.stream`` attribute chain keeps the guard
    robust against the receiver being ``self.client`` vs ``self._client``.
    """
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in {"create", "stream"}:
            continue
        receiver = func.value
        if isinstance(receiver, ast.Attribute) and receiver.attr == "messages":
            calls.append(node)
    return calls


def _model_keyword(call: ast.Call) -> ast.keyword | None:
    """Return the ``model=`` keyword node of a call, or None if absent."""
    for kw in call.keywords:
        if kw.arg == "model":
            return kw
    return None


def _is_settings_anthropic_model(node: ast.expr) -> bool:
    """True iff ``node`` is exactly the ``self.settings.anthropic_model`` chain."""
    if not isinstance(node, ast.Attribute) or node.attr != "anthropic_model":
        return False
    settings_attr = node.value
    if not isinstance(settings_attr, ast.Attribute) or settings_attr.attr != "settings":
        return False
    self_name = settings_attr.value
    return isinstance(self_name, ast.Name) and self_name.id == "self"


def _service_with_mock_create(response_text: str) -> tuple[ThinkerService, AsyncMock]:
    """Build a ThinkerService whose client's ``messages.create`` is mocked.

    Self-contained (does not import test_thinker_service internals) so this
    regression file stands on its own. Returns (service, mock_client) so the
    caller can assert on ``mock_client.messages.create.call_args``.
    """
    service = ThinkerService()
    mock_response = create_mock_anthropic_response(response_text)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    service._client = mock_client
    return service, mock_client


def _mock_thinker(
    name: str = "Socrates",
    bio: str = "Ancient Greek philosopher",
    positions: str = "Socratic method",
    style: str = "Questions everything",
) -> MagicMock:
    """Minimal ConversationThinker stand-in for response-generation calls."""
    thinker = MagicMock()
    thinker.name = name
    thinker.bio = bio
    thinker.positions = positions
    thinker.style = style
    return thinker


def _mock_user_message(content: str = "What is truth?") -> MagicMock:
    message = MagicMock()
    message.sender_type = SenderType.USER
    message.sender_name = "Alice"
    message.content = content
    return message


# ===========================================================================
# TestAnthropicModelConfigContract
# Regression guard for fix #978 / #973 (commit 6860aa4) -- the config field
# that is the single source of truth for the thinker model id.
# ===========================================================================


class TestAnthropicModelConfigContract:
    """Guards: ``settings.anthropic_model`` is a non-dated, env-overridable str."""

    def test_settings_exposes_anthropic_model_as_str(self) -> None:
        """The centralized config field exists and is a string.

        If a refactor dropped the field, the five thinker call sites that read
        ``self.settings.anthropic_model`` would raise ``AttributeError`` on the
        first API call -- so the field's very existence is load-bearing.
        """
        settings = Settings()
        assert hasattr(settings, "anthropic_model")
        assert isinstance(settings.anthropic_model, str)
        assert settings.anthropic_model  # non-empty

    def test_default_model_is_not_any_dated_snapshot(self) -> None:
        """The default must be a rolling alias, never an 8-digit dated snapshot.

        The exact retired literal is guarded by the merged ``test_config`` suite;
        this is the broader invariant -- *no* dated snapshot (``...-YYYYMMDD``)
        may be the default, because every dated snapshot eventually retires and
        starts 404ing. Pins the regression class, not just the one instance.
        """
        settings = Settings()
        assert settings.anthropic_model != _RETIRED_SNAPSHOT
        assert _DATED_SNAPSHOT_RE.search(settings.anthropic_model) is None

    def test_anthropic_model_overridable_via_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The model id is overridable via the ``ANTHROPIC_MODEL`` env var.

        Production overrides the model without a code change; the merged suite
        only proves constructor-kwarg override, not the env path that Railway
        actually uses. ``case_sensitive=False`` means the upper-case env name
        maps onto the field.
        """
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")
        settings = Settings()
        assert settings.anthropic_model == "claude-opus-4-8"

    def test_thinker_service_reads_model_from_its_settings(self) -> None:
        """A fresh ThinkerService carries the config field on ``self.settings``.

        The call sites read ``self.settings.anthropic_model``; this proves the
        service wires the settings object that exposes that attribute, so the
        config field and the call-site access path are the same thing.
        """
        service = ThinkerService()
        assert service.settings.anthropic_model == Settings().anthropic_model


# ===========================================================================
# TestThinkerModelCentralizationSource
# Regression guard for fix #978 (commit 6860aa4) -- source-level proof that the
# centralization is total: every Anthropic call reads the config, and no dated
# snapshot literal survives anywhere in thinker.py. These fail on a refactor
# that re-hardcodes a model id even when every behavioural test stays green.
# ===========================================================================


class TestThinkerModelCentralizationSource:
    """Source/AST guards: all model ids in thinker.py flow from config."""

    def test_retired_snapshot_literal_absent_from_source(self) -> None:
        """The specific retired 404ing snapshot appears nowhere in the module.

        This is the literal that broke production; its reappearance anywhere in
        ``thinker.py`` -- even a comment or docstring would be suspicious -- is a
        direct regression signal.
        """
        assert _RETIRED_SNAPSHOT not in _THINKER_SOURCE

    def test_no_dated_snapshot_literal_in_any_string_constant(self) -> None:
        """No string literal in thinker.py is a dated Anthropic snapshot.

        Walks every string constant in the AST (so it ignores incidental digit
        runs in identifiers) and asserts none matches ``claude-...-YYYYMMDD``.
        Guards the whole regression *class*: any dated snapshot, not just the
        one that already retired.
        """
        offenders = [
            node.value
            for node in ast.walk(_THINKER_TREE)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _DATED_SNAPSHOT_RE.search(node.value)
        ]
        assert offenders == [], f"Dated model snapshot literal(s) found: {offenders}"

    def test_every_anthropic_call_passes_model_from_settings(self) -> None:
        """Every ``messages.create``/``stream`` call uses ``self.settings.anthropic_model``.

        The AST guard is stronger than any single behavioural test: it proves
        *all* call sites are centralized at once, including the streaming path
        that is impractical to exercise behaviourally. A call site that switched
        back to a string constant (or any other expression) fails here.
        """
        calls = _iter_anthropic_calls(_THINKER_TREE)
        for call in calls:
            kw = _model_keyword(call)
            assert kw is not None, f"Anthropic call at line {call.lineno} is missing a model= kwarg"
            assert not isinstance(kw.value, ast.Constant), (
                f"Anthropic call at line {call.lineno} hardcodes a model literal"
            )
            assert _is_settings_anthropic_model(kw.value), (
                f"Anthropic call at line {call.lineno} does not read self.settings.anthropic_model"
            )

    def test_all_anthropic_calls_carry_an_explicit_model_kwarg(self) -> None:
        """No Anthropic call relies on an implicit/default model.

        Complements the previous test: even before checking *what* the model is,
        every create/stream call must name ``model=`` explicitly so the SDK's
        own default can never silently take over.
        """
        calls = _iter_anthropic_calls(_THINKER_TREE)
        assert calls, "Expected to find Anthropic messages.create/stream call sites"
        missing = [c.lineno for c in calls if _model_keyword(c) is None]
        assert missing == [], f"Anthropic calls missing model= kwarg at lines {missing}"

    def test_expected_centralized_model_call_site_count(self) -> None:
        """Exactly five Anthropic call sites are centralized on the config.

        The fix replaced five hardcoded copies. Pinning the count means a
        *new* call site that forgets to read the config (count rises with an
        uncentralized one) or a dropped call site (count falls) both surface
        here as a deliberate, reviewed change rather than a silent drift.
        """
        centralized = [
            call
            for call in _iter_anthropic_calls(_THINKER_TREE)
            if (kw := _model_keyword(call)) is not None and _is_settings_anthropic_model(kw.value)
        ]
        assert len(centralized) == 5, (
            f"Expected 5 centralized Anthropic call sites, found {len(centralized)} "
            f"at lines {[c.lineno for c in centralized]}"
        )


# ===========================================================================
# TestThinkerModelCentralizationBehavioral
# Regression guard for fix #978 (commit 6860aa4) -- behavioural proof that the
# configured model id reaches the API kwargs for the four call sites the merged
# fix never pinned (it only covered validate_thinker). Each test sets a sentinel
# model on the service settings and asserts the mocked client received it.
# ===========================================================================


_SENTINEL_MODEL = "claude-regression-sentinel-xyz"


class TestThinkerModelCentralizationBehavioral:
    """Per-call-site guards: configured model reaches the Anthropic API call."""

    async def test_suggest_thinkers_single_batch_uses_configured_model(self) -> None:
        """``suggest_thinkers`` (count<=2 single-batch path) sends the config model.

        ``_suggest_single_batch`` (line 314 call site) backs the small-count
        path and was never behaviourally pinned by the merged fix.
        """
        json_text = create_mock_thinker_suggestion_json(
            name="Socrates",
            reason="Master of questioning",
            bio="Ancient Greek philosopher",
            positions="Socratic method",
            style="Questions everything",
        )
        service, mock_client = _service_with_mock_create(json_text)
        service.settings.anthropic_model = _SENTINEL_MODEL

        await service.suggest_thinkers("philosophy", 1)

        mock_client.messages.create.assert_awaited()
        used_model = mock_client.messages.create.call_args.kwargs["model"]
        assert used_model == _SENTINEL_MODEL
        assert used_model != _RETIRED_SNAPSHOT

    async def test_suggest_thinkers_parallel_batches_use_configured_model(self) -> None:
        """The parallel (count>2) suggestion path also sends the config model.

        ``suggest_thinkers`` fans out into several ``_suggest_single_batch``
        tasks for larger counts; every fan-out call must still read the config,
        not a hardcoded snapshot.
        """
        json_text = create_mock_thinker_suggestion_json(
            name="Socrates",
            reason="Master of questioning",
            bio="Ancient Greek philosopher",
            positions="Socratic method",
            style="Questions everything",
        )
        service, mock_client = _service_with_mock_create(json_text)
        service.settings.anthropic_model = _SENTINEL_MODEL

        await service.suggest_thinkers("philosophy", 4)

        mock_client.messages.create.assert_awaited()
        # Every fan-out call -- not just the first -- must use the config model.
        for call in mock_client.messages.create.call_args_list:
            assert call.kwargs["model"] == _SENTINEL_MODEL

    async def test_generate_response_uses_configured_model(self) -> None:
        """``generate_response`` (non-streaming fallback) sends the config model.

        Line 1040 call site -- the production fallback when streaming is
        unavailable -- was not pinned by the merged fix.
        """
        service, mock_client = _service_with_mock_create("I think therefore I am.")
        service.settings.anthropic_model = _SENTINEL_MODEL

        thinker = _mock_thinker("Descartes", "French philosopher", "Rationalism", "Doubt")
        messages: Any = [_mock_user_message("What is existence?")]

        await service.generate_response(thinker, messages, "philosophy")

        mock_client.messages.create.assert_awaited()
        used_model = mock_client.messages.create.call_args.kwargs["model"]
        assert used_model == _SENTINEL_MODEL
        assert used_model != _RETIRED_SNAPSHOT

    async def test_generate_user_prompt_uses_configured_model(self) -> None:
        """``generate_user_prompt`` sends the config model.

        Line 1526 call site -- the "invite the quiet user back" prompt -- was
        not pinned by the merged fix.
        """
        service, mock_client = _service_with_mock_create("Alice, what do you think?")
        service.settings.anthropic_model = _SENTINEL_MODEL

        thinker = _mock_thinker()
        messages: Any = [_mock_user_message("What is truth?")]

        await service.generate_user_prompt(thinker, messages, "philosophy", "Alice")

        mock_client.messages.create.assert_awaited()
        used_model = mock_client.messages.create.call_args.kwargs["model"]
        assert used_model == _SENTINEL_MODEL
        assert used_model != _RETIRED_SNAPSHOT
