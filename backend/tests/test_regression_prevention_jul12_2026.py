"""Regression prevention tests for Sunday QA (July 12, 2026).

Focus: lock in the centralized-Anthropic-model fix (#978, commit 6860aa4) so a
future refactor cannot silently reintroduce the exact production outage it fixed.

Background — what #978 fixed
----------------------------
``thinker.py`` calls the Anthropic API from **five** distinct code paths:

  1. ``_suggest_single_batch``                 (thinker suggestions)
  2. ``validate_thinker``                       (thinker name validation)
  3. ``generate_response_with_streaming_thinking`` (streaming reply)
  4. ``generate_response``                      (non-streaming reply fallback)
  5. ``generate_user_prompt``                   (invite-the-user message)

Before #978 each of the five call sites hard-coded the dated model snapshot
``claude-sonnet-4-20250514``. Anthropic retired that snapshot, so every call
started returning ``404 not_found_error`` — breaking thinker suggestions in
production and ~9 E2E tests on any PR that ran the E2E suite. #978 replaced all
five literals with a single source of truth: ``settings.anthropic_model``
(default ``claude-sonnet-4-6``, overridable via env / issue #973).

Why this file exists
--------------------
#978 shipped guards for only **one** of the five call sites
(``test_validate_uses_configured_anthropic_model``) plus the config default.
The other four call sites — including the suggestion path that actually took
down production — have no guard. A refactor (or a copy-paste of the old code)
could re-hardcode a dated snapshot in ``_suggest_single_batch``,
``generate_response``, ``generate_response_with_streaming_thinking``, or
``generate_user_prompt`` and every existing behavioral test would stay green
until the next model retirement silently broke production again.

These tests pin the invariant three ways so the regression cannot slip back in
through any single gap:

- **Structural (AST):** *every* ``client.messages.create`` / ``.stream`` call in
  ``thinker.py`` passes ``model=self.settings.anthropic_model`` — not a literal.
  This catches a re-hardcode in *any* call site, present or future.
- **Behavioral:** the three untested non-streaming call sites
  (``_suggest_single_batch``, ``generate_response``, ``generate_user_prompt``)
  demonstrably forward the configured model to the API at run time.
- **Config contract:** the default model is a current alias, never a dated
  ``-YYYYMMDD`` snapshot (the failure mode that caused the outage), and it stays
  overridable.

Test groups (this file, 12 tests total):
- TestAnthropicModelSingleSourceOfTruth (4): AST/source structural guards
- TestThinkerCallSitesUseConfiguredModel (5): behavioral per-call-site guards
- TestAnthropicModelDefaultContract (3): config default / override contract
"""

import ast
import inspect
import re
from collections.abc import Awaitable, Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from anthropic.types import TextBlock

from app.core.config import Settings, get_settings
from app.models.message import SenderType
from app.services import thinker as thinker_module
from app.services.thinker import ThinkerService


@pytest.fixture(autouse=True)
def restore_configured_model() -> Generator[None, None, None]:
    """Restore the cached settings' anthropic_model after each test.

    ``get_settings()`` is ``@lru_cache``d, so every ThinkerService shares one
    Settings instance. Several tests below set ``settings.anthropic_model`` to a
    sentinel to observe it on the API call; without restoration that sentinel
    would leak into other test files that read the default model. Snapshot and
    restore the value so this file has no cross-test side effects.
    """
    original = get_settings().anthropic_model
    yield
    get_settings().anthropic_model = original


# A dated model snapshot looks like ``claude-<family>-<major>-YYYYMMDD``. The
# retired one that caused the #973/#978 outage was ``claude-sonnet-4-20250514``.
# Any 8-digit date suffix on a claude id is the exact failure pattern we forbid
# from reappearing as a hard-coded string in the thinker service.
_DATED_SNAPSHOT_RE = re.compile(r"claude-[a-z0-9]+-\d+-\d{8}")
_RETIRED_SNAPSHOT = "claude-sonnet-4-20250514"
# The single source of truth expression every API call site must use.
_CONFIGURED_MODEL_EXPR = "self.settings.anthropic_model"


def _messages_api_calls(tree: ast.AST) -> list[ast.Call]:
    """Return every ``<...>.messages.create`` / ``.stream`` Call node in a tree.

    Matches the two shapes used in thinker.py:
        await self.client.messages.create(...)
        async with self.client.messages.stream(...) as stream:
    by finding Call nodes whose function is ``<x>.messages.create`` or
    ``<x>.messages.stream``.
    """
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in {"create", "stream"}:
            continue
        # The receiver of .create/.stream must itself be a `.messages` attribute
        # access, i.e. `<something>.messages.create(...)`.
        receiver = func.value
        if isinstance(receiver, ast.Attribute) and receiver.attr == "messages":
            calls.append(node)
    return calls


def _make_mock_client(response_text: str) -> AsyncMock:
    """Build a mock Anthropic client whose messages.create returns response_text.

    Self-contained (does not import test_thinker_service) so this regression
    file has no cross-test-module dependencies.
    """
    mock_response = MagicMock()
    mock_response.content = [TextBlock(type="text", text=response_text)]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 10
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


def _make_mock_thinker() -> MagicMock:
    """A minimally-configured thinker for generate_* call-site tests."""
    thinker = MagicMock()
    thinker.name = "Socrates"
    thinker.bio = "Ancient Greek philosopher"
    thinker.positions = "The Socratic method"
    thinker.style = "Relentless questioning"
    return thinker


# ===========================================================================
# TestAnthropicModelSingleSourceOfTruth
# Structural (AST + source) guards for fix #978 (commit 6860aa4).
#
# These are the "reviewer aid" guards: they fail the instant anyone re-hardcodes
# a model id in ANY of the five thinker.py API call sites, without needing to
# exercise each path behaviorally.
# ===========================================================================


class TestAnthropicModelSingleSourceOfTruth:
    """Structural guards: all thinker.py API calls use settings.anthropic_model."""

    def test_no_hardcoded_dated_model_snapshot_in_thinker(self) -> None:
        """thinker.py contains no hard-coded dated ``claude-*-YYYYMMDD`` snapshot.

        Regression guard for #978: the outage was caused by dated snapshots
        (``claude-sonnet-4-20250514``) hard-coded across five call sites. Dated
        snapshots get retired and start returning 404, so none must appear as a
        literal in the service — the model id must come from config instead.
        """
        source = inspect.getsource(thinker_module)
        matches = _DATED_SNAPSHOT_RE.findall(source)
        assert matches == [], (
            f"thinker.py must not hard-code a dated model snapshot "
            f"(claude-*-YYYYMMDD); such snapshots get retired and 404. Found "
            f"{matches}. Source the model from settings.anthropic_model instead "
            f"(#978)."
        )

    def test_retired_snapshot_string_absent_from_thinker(self) -> None:
        """The specific retired snapshot ``claude-sonnet-4-20250514`` is gone.

        Regression guard for #978: pin the exact literal that caused the outage
        so a copy-paste of the pre-fix code is rejected with an obvious message,
        even if some future dated snapshot didn't match the general pattern.
        """
        source = inspect.getsource(thinker_module)
        assert _RETIRED_SNAPSHOT not in source, (
            f"thinker.py must not reference the retired snapshot "
            f"{_RETIRED_SNAPSHOT!r} — it returns 404 from the Anthropic API and "
            f"broke thinker suggestions in production (#973/#978)."
        )

    def test_every_messages_api_call_uses_configured_model(self) -> None:
        """AST: every messages.create/.stream call passes settings.anthropic_model.

        Regression guard for #978: this is the load-bearing structural check. It
        walks the whole module AST, finds all five ``client.messages.create`` /
        ``.stream`` call sites, and asserts each one passes
        ``model=self.settings.anthropic_model`` — a literal or a divergent
        expression fails immediately, no matter which call site regressed.
        """
        source = inspect.getsource(thinker_module)
        tree = ast.parse(source)
        calls = _messages_api_calls(tree)
        assert len(calls) == 5, (
            f"Expected 5 Anthropic messages.create/.stream call sites in "
            f"thinker.py (suggest, validate, streaming, generate_response, "
            f"generate_user_prompt); found {len(calls)}. If the count changed, "
            f"a call site was added/removed — extend this guard so the new site "
            f"is covered (#978)."
        )
        offenders: list[str] = []
        for call in calls:
            model_kw = next((kw for kw in call.keywords if kw.arg == "model"), None)
            if model_kw is None:
                offenders.append(f"line {call.lineno}: no model= keyword")
                continue
            expr = ast.unparse(model_kw.value)
            if expr != _CONFIGURED_MODEL_EXPR:
                offenders.append(f"line {call.lineno}: model={expr}")
        assert offenders == [], (
            f"Every Anthropic API call in thinker.py must pass "
            f"model={_CONFIGURED_MODEL_EXPR!r} (single source of truth, #978). "
            f"Offending call sites: {offenders}."
        )

    def test_configured_model_expression_used_five_times(self) -> None:
        """The configured-model expression appears exactly once per call site.

        Regression guard for #978: belt-and-suspenders with the AST walk. A
        plain-text count of ``model=self.settings.anthropic_model`` must equal
        the five call sites. If someone adds a sixth API call but forgets to use
        the configured model, this count diverges from the AST call count and
        the pair of tests brackets the regression.
        """
        source = inspect.getsource(thinker_module)
        occurrences = source.count(f"model={_CONFIGURED_MODEL_EXPR}")
        assert occurrences == 5, (
            f"Expected 5 uses of 'model={_CONFIGURED_MODEL_EXPR}' in thinker.py "
            f"(one per API call site), found {occurrences}. A mismatch means a "
            f"call site stopped using the centralized model id (#978)."
        )


# ===========================================================================
# TestThinkerCallSitesUseConfiguredModel
# Behavioral guards for the four call sites #978 did NOT test.
#
# #978 only added test_validate_uses_configured_anthropic_model. These exercise
# the remaining non-streaming call sites at run time, proving the configured
# model id is actually forwarded to the Anthropic API — not just referenced in
# source. The streaming path is covered structurally by the AST guard above
# (mocking messages.stream's async-context-manager is brittle and adds no signal
# beyond the AST check).
# ===========================================================================


class TestThinkerCallSitesUseConfiguredModel:
    """Behavioral guards: each thinker call site forwards settings.anthropic_model."""

    async def test_suggest_single_batch_uses_configured_model(self) -> None:
        """_suggest_single_batch forwards the configured model to messages.create.

        Regression guard for #978: this is the path that actually 404'd in
        production. A sentinel model id set on settings must reach the API call,
        proving the suggestion path reads settings.anthropic_model rather than a
        hard-coded snapshot.
        """
        import json

        payload = json.dumps(
            [
                {
                    "name": "Socrates",
                    "reason": "Foundational ethicist",
                    "profile": {
                        "name": "Socrates",
                        "bio": "Ancient Greek philosopher",
                        "positions": "The examined life",
                        "style": "Questions everything",
                    },
                }
            ]
        )
        service = ThinkerService()
        mock_client = _make_mock_client(payload)
        service._client = mock_client
        service.settings.anthropic_model = "claude-sentinel-suggest"

        await service._suggest_single_batch("ethics", 1)

        mock_client.messages.create.assert_awaited()
        used_model = mock_client.messages.create.call_args.kwargs["model"]
        assert used_model == "claude-sentinel-suggest", (
            f"_suggest_single_batch must call the API with the configured model "
            f"(settings.anthropic_model), got {used_model!r}. This is the path "
            f"that 404'd in production before #978."
        )
        assert used_model != _RETIRED_SNAPSHOT

    async def test_generate_response_uses_configured_model(self) -> None:
        """generate_response forwards the configured model to messages.create.

        Regression guard for #978: the non-streaming reply fallback must source
        its model from settings, or a retired snapshot here would silently break
        replies whenever the streaming path also failed.
        """
        service = ThinkerService()
        mock_client = _make_mock_client("I only know that I know nothing.")
        service._client = mock_client
        service.settings.anthropic_model = "claude-sentinel-response"

        thinker = _make_mock_thinker()
        message = MagicMock()
        message.sender_type = SenderType.USER
        message.sender_name = "Alice"
        message.content = "What is virtue?"
        messages: Any = [message]

        await service.generate_response(thinker, messages, "ethics")

        used_model = mock_client.messages.create.call_args.kwargs["model"]
        assert used_model == "claude-sentinel-response", (
            f"generate_response must call the API with settings.anthropic_model, "
            f"got {used_model!r} (#978)."
        )
        assert used_model != _RETIRED_SNAPSHOT

    async def test_generate_user_prompt_uses_configured_model(self) -> None:
        """generate_user_prompt forwards the configured model to messages.create.

        Regression guard for #978: the invite-the-user path must also read the
        centralized model id so no call site keeps a stale snapshot behind.
        """
        service = ThinkerService()
        mock_client = _make_mock_client("Alice, what do you make of this?")
        service._client = mock_client
        service.settings.anthropic_model = "claude-sentinel-prompt"

        thinker = _make_mock_thinker()
        message = MagicMock()
        message.sender_type = SenderType.USER
        message.sender_name = "Alice"
        message.content = "I am not sure."
        messages: Any = [message]

        await service.generate_user_prompt(thinker, messages, "ethics", "Alice")

        used_model = mock_client.messages.create.call_args.kwargs["model"]
        assert used_model == "claude-sentinel-prompt", (
            f"generate_user_prompt must call the API with settings.anthropic_model, "
            f"got {used_model!r} (#978)."
        )
        assert used_model != _RETIRED_SNAPSHOT

    async def test_call_sites_share_one_model_value(self) -> None:
        """All non-streaming call sites read the SAME configured value.

        Regression guard for #978: the point of centralization is that one
        config change updates every call site at once. Setting a single sentinel
        and driving three different code paths must produce the same model on
        each API call — proving they share one source of truth, not three
        coincidentally-equal literals.
        """
        import json

        suggest_payload = json.dumps(
            [
                {
                    "name": "Kant",
                    "reason": "Deontologist",
                    "profile": {
                        "name": "Kant",
                        "bio": "German philosopher",
                        "positions": "Categorical imperative",
                        "style": "Systematic",
                    },
                }
            ]
        )
        thinker = _make_mock_thinker()
        message = MagicMock()
        message.sender_type = SenderType.USER
        message.sender_name = "Bob"
        message.content = "Is lying ever right?"
        messages: Any = [message]

        seen_models: set[str] = set()

        drivers: list[tuple[str, Callable[[ThinkerService], Awaitable[Any]]]] = [
            (suggest_payload, lambda s: s._suggest_single_batch("ethics", 1)),
            ("A reply.", lambda s: s.generate_response(thinker, messages, "ethics")),
            (
                "Bob, your view?",
                lambda s: s.generate_user_prompt(thinker, messages, "ethics", "Bob"),
            ),
        ]
        for payload, driver in drivers:
            service = ThinkerService()
            mock_client = _make_mock_client(payload)
            service._client = mock_client
            service.settings.anthropic_model = "claude-shared-sentinel"
            await driver(service)
            seen_models.add(mock_client.messages.create.call_args.kwargs["model"])

        assert seen_models == {"claude-shared-sentinel"}, (
            f"All non-streaming call sites must read the same "
            f"settings.anthropic_model value; observed {seen_models}. Divergence "
            f"means a call site kept its own model id instead of the centralized "
            f"one (#978)."
        )

    async def test_generate_response_without_client_makes_no_api_call(self) -> None:
        """With no client, generate_response returns empty and calls no API.

        Regression guard for #978: the model-forwarding tests above rely on the
        API being reached. This pins the complementary short-circuit so a future
        change that always instantiates a client (and would then need the model
        guard) can't quietly bypass the ``if not self.client`` guard.
        """
        service = ThinkerService()
        thinker = _make_mock_thinker()
        messages: Any = []

        with patch.object(type(service), "client", new_callable=PropertyMock) as mock_client:
            mock_client.return_value = None
            response, cost = await service.generate_response(thinker, messages, "ethics")

        assert response == ""
        assert cost == 0.0


# ===========================================================================
# TestAnthropicModelDefaultContract
# Config-level guards for fix #978 (commit 6860aa4).
#
# #978 pinned the exact default (== "claude-sonnet-4-6"). These add the broader
# invariant that matters for preventing the outage class: the default is never a
# dated snapshot, and it stays overridable so ops can roll forward without a
# code change when the next snapshot is retired.
# ===========================================================================


class TestAnthropicModelDefaultContract:
    """Config guards: anthropic_model default is a live, overridable alias."""

    def test_default_model_is_not_a_dated_snapshot(self) -> None:
        """The default anthropic_model is not a dated ``-YYYYMMDD`` snapshot.

        Regression guard for #978: #978 pins the exact default value; this pins
        the *shape* invariant that prevents the whole outage class — a dated
        snapshot default would inevitably be retired and 404 the moment
        Anthropic sunset it. Aliases (e.g. ``claude-sonnet-4-6``) don't rot.
        """
        default = Settings().anthropic_model
        assert not _DATED_SNAPSHOT_RE.fullmatch(default), (
            f"Default anthropic_model {default!r} looks like a dated snapshot "
            f"(claude-*-YYYYMMDD). Dated snapshots get retired and 404; the "
            f"default must be a rolling alias (#978)."
        )
        assert default != _RETIRED_SNAPSHOT

    def test_default_model_is_a_nonempty_claude_id(self) -> None:
        """The default anthropic_model is a non-empty Claude model id.

        Regression guard for #978: a blank or non-Claude default would make
        every thinker API call fail. The centralized default must be a usable
        Claude id out of the box.
        """
        default = Settings().anthropic_model
        assert isinstance(default, str) and default.startswith("claude-"), (
            f"Default anthropic_model must be a non-empty Claude id "
            f"(starts with 'claude-'); got {default!r} (#978)."
        )

    async def test_model_is_overridable_and_reaches_service(self) -> None:
        """An overridden anthropic_model propagates through to a service call.

        Regression guard for #978: centralization is only useful if the override
        actually drives the API call. This wires an override end-to-end — set on
        the settings a service uses, then observed on the real API call — closing
        the loop between config and call site that #978's config-only test leaves
        open.
        """
        override = Settings(anthropic_model="claude-opus-4-8")
        assert override.anthropic_model == "claude-opus-4-8"

        service = ThinkerService()
        mock_client = _make_mock_client("A reply.")
        service._client = mock_client
        service.settings.anthropic_model = override.anthropic_model

        thinker = _make_mock_thinker()
        message = MagicMock()
        message.sender_type = SenderType.USER
        message.sender_name = "Ada"
        message.content = "Define justice."
        messages: Any = [message]

        await service.generate_response(thinker, messages, "ethics")
        assert mock_client.messages.create.call_args.kwargs["model"] == "claude-opus-4-8"
