"""Regression prevention tests for Sunday QA (May 17, 2026).

Focus areas: pin down behavioral contracts from recent bug fixes that lack
explicit regression guards in the existing test suites.

Each test class documents the original bug, the fix commit, and the specific
invariant being guarded so that future agents understand WHY the test exists.

Bug fixes covered:
- fix(feedback): use enum values instead of names for PostgreSQL (#299, 451a962)
  Without values_callable, SQLAlchemy stores enum member names (FEATURE, BUG)
  instead of lowercase values (feature, bug), causing PostgreSQL enum mismatch.
- feat(backend): add idle timeout to auto-pause inactive conversations
  (#483, 7aa14e7). The WSMessageType.IDLE_TIMEOUT constant and the
  cross-state contracts between manual pause and idle pause must remain intact.
- fix(websocket): sync pause button state when switching threads
  (#367, a9c7742). The connect handler always sends current pause state.
- feat(thinker): @mention support for addressing specific thinkers
  (#257, 363f0e7). extract_mentions and is_mentioned have edge-case
  behaviors that downstream `_should_respond` and `_choose_response_style`
  rely on (e.g., empty input, plain text, deduplication).
- fix: persist language preference to database (#81, 6fb8b6c). The
  `_get_language_instruction("en")` returning empty string is load-bearing
  for prompt generation — non-empty would inject an "IMPORTANT: Respond in
  English" line into every English prompt and waste tokens.

Test groups (this file):
- TestFeedbackEnumValuesCallable (6): Enum columns serialize lowercase values
- TestFeedbackTablenameContract (2): Table name pluralization
- TestWSMessageTypeConstants (6): String constants must keep their wire values
- TestIdlePauseCrossStateContract (5): manual pause / idle pause interactions
- TestExtractMentionsBasicContract (5): empty/plain/dedup behaviors
- TestIsMentionedCaseInsensitivity (3): case folding contract
- TestLanguageInstructionEnglishBypass (3): English returns empty (token saver)
- TestSplitBubblesEmptyAndShort (4): boundary behavior for bubble splitting
"""

from sqlalchemy import Enum as SAEnum

from app.api.websocket import WSMessageType
from app.core.config import get_settings
from app.models.feedback import Feedback, FeedbackStatus, FeedbackType
from app.services.thinker import (
    ThinkerService,
    _get_language_instruction,
    extract_mentions,
    is_mentioned,
)

# ===========================================================================
# TestFeedbackEnumValuesCallable
# Regression guard for commit 451a962 (fix #299).
#
# Bug: SQLAlchemy's default Enum column behavior stores the enum MEMBER NAME
# (e.g., "BUG", "FEATURE") in PostgreSQL. Combined with a PostgreSQL ENUM type
# whose labels are the lowercase VALUES ("bug", "feature"), inserts failed with:
#     invalid input value for enum feedbacktype: "FEATURE"
#
# Fix: Pass `values_callable=lambda x: [e.value for e in x]` to the SAEnum
# column so SQLAlchemy serializes using the lowercase string values.
#
# If `values_callable` were removed (or the enum value casing changed),
# production inserts would 500 on every feedback submission. These tests
# pin down the contract via direct column introspection rather than requiring
# a PostgreSQL instance.
# ===========================================================================


class TestFeedbackEnumValuesCallable:
    """Regression tests: Feedback Enum columns use values_callable for PG compat."""

    def test_feedback_type_column_has_values_callable(self) -> None:
        """feedback_type column's SAEnum has a values_callable producing lowercase.

        Regression guard: without values_callable, SQLAlchemy defaults to the
        enum member names ("BUG", "FEATURE", "OTHER") which mismatch the
        PostgreSQL feedbacktype enum labels ("bug", "feature", "other").
        """
        column = Feedback.__table__.c.feedback_type
        enum_type = column.type
        assert isinstance(enum_type, SAEnum), (
            f"feedback_type column should use SQLAlchemy Enum, got {type(enum_type)}"
        )
        # The .enums attribute holds the resolved list of labels SQLAlchemy
        # will write to PostgreSQL. After values_callable, these must be
        # lowercase values, NOT uppercase names.
        labels = list(enum_type.enums)
        assert labels == ["bug", "feature", "other"], (
            f"feedback_type labels must be lowercase values for PG compat. "
            f"Got {labels!r}. The values_callable kwarg has likely regressed."
        )

    def test_feedback_status_column_has_values_callable(self) -> None:
        """status column's SAEnum has a values_callable producing lowercase.

        Same regression guard as feedback_type — values_callable ensures
        SQLAlchemy writes lowercase enum labels matching the PostgreSQL type.
        """
        column = Feedback.__table__.c.status
        enum_type = column.type
        assert isinstance(enum_type, SAEnum)
        labels = list(enum_type.enums)
        assert labels == ["new", "reviewed", "resolved"], (
            f"status labels must be lowercase values for PG compat. "
            f"Got {labels!r}. The values_callable kwarg has likely regressed."
        )

    def test_feedback_type_enum_values_are_lowercase(self) -> None:
        """FeedbackType.BUG.value == 'bug' (lowercase string).

        The values_callable fix depends on enum VALUES being lowercase. If
        someone changed BUG = "BUG" (uppercase), the PG enum mismatch returns.
        """
        assert FeedbackType.BUG.value == "bug"
        assert FeedbackType.FEATURE.value == "feature"
        assert FeedbackType.OTHER.value == "other"

    def test_feedback_status_enum_values_are_lowercase(self) -> None:
        """FeedbackStatus enum values are lowercase strings."""
        assert FeedbackStatus.NEW.value == "new"
        assert FeedbackStatus.REVIEWED.value == "reviewed"
        assert FeedbackStatus.RESOLVED.value == "resolved"

    def test_feedback_type_postgres_enum_name(self) -> None:
        """feedback_type column uses 'feedbacktype' as the PG enum type name.

        Regression guard: the explicit `name="feedbacktype"` kwarg ensures
        SQLAlchemy uses a predictable PG enum type name. Auto-generated names
        could include the column prefix and break alembic migrations.
        """
        column = Feedback.__table__.c.feedback_type
        enum_type = column.type
        assert isinstance(enum_type, SAEnum)
        assert enum_type.name == "feedbacktype", (
            f"feedback_type PG enum name should be 'feedbacktype', got {enum_type.name!r}"
        )

    def test_feedback_status_postgres_enum_name(self) -> None:
        """status column uses 'feedbackstatus' as the PG enum type name."""
        column = Feedback.__table__.c.status
        enum_type = column.type
        assert isinstance(enum_type, SAEnum)
        assert enum_type.name == "feedbackstatus", (
            f"status PG enum name should be 'feedbackstatus', got {enum_type.name!r}"
        )


# ===========================================================================
# TestFeedbackTablenameContract
# Regression guard: the Feedback table is named "feedbacks" (plural). An
# accidental rename to "feedback" (singular) would orphan production data
# and break alembic migrations.
# ===========================================================================


class TestFeedbackTablenameContract:
    """Regression tests: Feedback table name stays 'feedbacks' (plural)."""

    def test_feedback_tablename_is_plural(self) -> None:
        """Feedback.__tablename__ == 'feedbacks' (not 'feedback').

        Regression guard: production data lives in the 'feedbacks' table.
        Renaming to singular would require a migration AND silently orphan
        all existing rows until that migration ran.
        """
        assert Feedback.__tablename__ == "feedbacks"

    def test_feedback_table_object_matches_tablename(self) -> None:
        """Feedback.__table__.name matches __tablename__ (no metadata drift)."""
        table = Feedback.__table__
        # __table__ is a sqlalchemy.Table which has a .name attribute
        assert getattr(table, "name", None) == "feedbacks"


# ===========================================================================
# TestWSMessageTypeConstants
# Regression guard: WSMessageType is a *wire protocol*. Changing a string
# value (e.g., "idle_timeout" -> "idleTimeout") breaks every existing
# frontend client without warning. These constants must be pinned.
#
# Particular focus on values added by recent commits:
#   - IDLE_TIMEOUT (7aa14e7, fix #483)
#   - SPEED_CHANGED (manager.set_speed_multiplier feature)
#   - CACHE_HIT (knowledge_research caching)
# ===========================================================================


class TestWSMessageTypeConstants:
    """Regression tests: wire-protocol WSMessageType string values are pinned."""

    def test_idle_timeout_value_is_snake_case(self) -> None:
        """WSMessageType.IDLE_TIMEOUT.value == 'idle_timeout'.

        Regression guard for feat #483: the frontend listens for the literal
        string 'idle_timeout' over the WebSocket. Changing this constant
        breaks every connected client silently — they just stop auto-pausing.
        """
        assert WSMessageType.IDLE_TIMEOUT.value == "idle_timeout"

    def test_paused_value_is_snake_case(self) -> None:
        """WSMessageType.PAUSED.value == 'paused' (used by pause sync fix #367)."""
        assert WSMessageType.PAUSED.value == "paused"

    def test_resumed_value_is_snake_case(self) -> None:
        """WSMessageType.RESUMED.value == 'resumed' (used by pause sync fix #367).

        The connect handler always sends RESUMED when the conversation is not
        paused (fix #367), so the frontend can sync after thread switches.
        """
        assert WSMessageType.RESUMED.value == "resumed"

    def test_speed_changed_value_is_snake_case(self) -> None:
        """WSMessageType.SPEED_CHANGED.value == 'speed_changed'."""
        assert WSMessageType.SPEED_CHANGED.value == "speed_changed"

    def test_cache_hit_value_is_snake_case(self) -> None:
        """WSMessageType.CACHE_HIT.value == 'cache_hit' (knowledge cache)."""
        assert WSMessageType.CACHE_HIT.value == "cache_hit"

    def test_wsmessagetype_is_string_enum(self) -> None:
        """WSMessageType inherits from str — enables JSON serialization.

        Regression guard: if someone refactors to plain `Enum` (not `str, Enum`),
        Pydantic's WSMessage serialization changes from "paused" to
        "WSMessageType.PAUSED", breaking the wire protocol.
        """
        # str enums compare equal to their value
        assert WSMessageType.PAUSED.value == "paused"
        assert isinstance(WSMessageType.PAUSED.value, str)
        # The enum member itself should also be a str instance (str-enum mixin)
        assert isinstance(WSMessageType.PAUSED, str)


# ===========================================================================
# TestIdlePauseCrossStateContract
# Regression guard for commit 7aa14e7 (feat #483).
#
# The fix introduced TWO state sets:
#   - _paused_conversations: set[str]
#   - _idle_paused_conversations: set[str]
#
# And the API contracts:
#   - pause_conversation()  → adds ONLY to _paused (manual pause)
#   - pause_for_idle()      → adds to BOTH (idle-pause is a kind of pause)
#   - is_paused()           → True if in EITHER set (cross-check)
#   - is_idle_paused()      → True only if in _idle_paused
#   - resume_conversation() → clears _paused (manual resume)
#   - resume_from_idle()    → no-op unless idle-paused; clears BOTH if so
#
# These cross-state contracts are subtle and easy to break. The mar29 and
# apr26 tests cover some paths; this set pins down the *remaining* paths that
# the existing suites don't explicitly assert.
# ===========================================================================


class TestIdlePauseCrossStateContract:
    """Regression tests: manual pause vs idle pause cross-state contracts."""

    def test_manual_pause_does_not_set_idle_paused(self) -> None:
        """pause_conversation must NOT mark a conv as idle-paused.

        Regression guard: if pause_conversation accidentally also added to
        _idle_paused_conversations, sending a user message would auto-resume
        a MANUALLY paused conversation — opposite of what the user requested.
        """
        service = ThinkerService()
        conv_id = "manual-not-idle-test"
        service.pause_conversation(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is False, (
            "Manual pause must NOT mark conversation as idle-paused; otherwise "
            "the next user message would auto-resume it via send_message handler."
        )

    def test_is_paused_returns_true_when_only_idle_paused(self) -> None:
        """is_paused must return True for idle-paused conversations.

        Regression guard: pause_for_idle adds to BOTH sets so is_paused works.
        If the dual-add invariant regressed, the agent loop wouldn't recognize
        idle-paused conversations as paused, and thinkers would keep responding
        despite the auto-pause.
        """
        service = ThinkerService()
        conv_id = "idle-implies-paused"
        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id) is True, (
            "is_paused must return True for idle-paused conversations — "
            "otherwise thinkers continue responding past the idle timeout."
        )
        assert service.is_idle_paused(conv_id) is True

    def test_pause_for_idle_is_idempotent(self) -> None:
        """Calling pause_for_idle twice does not error or double-add.

        Regression guard: the agent loop calls pause_for_idle inside a
        `if not self.is_idle_paused(...)` guard, but a defensive idempotency
        guarantee on pause_for_idle itself prevents subtle race conditions
        from breaking the conversation.
        """
        service = ThinkerService()
        conv_id = "idempotent-idle"
        service.pause_for_idle(conv_id)
        # Call again — must not raise and must leave state consistent
        service.pause_for_idle(conv_id)
        assert service.is_paused(conv_id) is True
        assert service.is_idle_paused(conv_id) is True

    def test_resume_from_idle_unknown_conversation_is_noop(self) -> None:
        """resume_from_idle for an unknown conversation does not raise.

        Regression guard: when the send_message endpoint calls
        resume_from_idle, the conversation might not be idle-paused at all
        (just a normal message during an active conversation). The function
        must be a safe no-op in this case.
        """
        service = ThinkerService()
        # Must not raise
        service.resume_from_idle("never-existed-conv-id")
        # State must remain empty
        assert service.is_paused("never-existed-conv-id") is False
        assert service.is_idle_paused("never-existed-conv-id") is False

    def test_idle_timeout_seconds_default_is_300(self) -> None:
        """The idle_timeout_seconds config default is 300 (5 minutes).

        Regression guard for feat #483: the documented default is 5 minutes.
        Changing it (e.g. to 0) silently disables the auto-pause feature in
        production without a migration or release note.
        """
        settings = get_settings()
        assert settings.idle_timeout_seconds == 300, (
            f"idle_timeout_seconds default must be 300s (5min), got "
            f"{settings.idle_timeout_seconds}. Setting to 0 disables auto-pause."
        )


# ===========================================================================
# TestExtractMentionsBasicContract
# Regression guard for commit 363f0e7 (feat #257).
#
# extract_mentions powers downstream is_mentioned, which powers the 0.98
# response-probability boost in _should_respond. Subtle behavior changes
# here (e.g., empty text raising, dedup regression) cause the @mention
# feature to silently break.
# ===========================================================================


class TestExtractMentionsBasicContract:
    """Regression tests: extract_mentions handles boundary inputs cleanly."""

    def test_empty_text_returns_empty_list(self) -> None:
        """extract_mentions('') returns [], not None or error.

        Regression guard: is_mentioned iterates `for mention in mentions`,
        which would crash if extract_mentions returned None.
        """
        assert extract_mentions("") == []

    def test_plain_text_without_at_sign_returns_empty(self) -> None:
        """extract_mentions('hello world') returns [].

        Regression guard: the regex patterns must require @ as anchor. If
        someone changed `@(\\w+)` to `(\\w+)`, every word would be a mention.
        """
        result = extract_mentions("hello world without any mentions here")
        assert result == [], (
            f"Plain text should produce no mentions; got {result!r}. "
            f"The @ anchor in the regex pattern has likely regressed."
        )

    def test_email_addresses_not_treated_as_mentions(self) -> None:
        """extract_mentions('contact me at user@example.com') captures 'example' only.

        Regression guard: emails contain @, but the @ in email is preceded by
        a word character (not space). The simple_pattern `@(\\w+)` still
        matches the part after the @ — this documents current behavior so
        any future "strict @-only" fix doesn't silently break agents
        depending on this string being captured.
        """
        result = extract_mentions("contact me at user@example.com")
        # Documents current behavior: "@example" is captured as a mention
        # (the .com part is filtered out because . is not a word character).
        # If you fix this so emails aren't matched, update this test.
        assert "example" in result, (
            "Current behavior captures the word after @ regardless of context. "
            "If this changed, agents may stop responding to '@user' in some flows."
        )

    def test_at_with_no_following_word_is_skipped(self) -> None:
        """extract_mentions('hello @ world') returns [] (bare @ has no word)."""
        # `@(\w+)` requires at least one word character after the @
        result = extract_mentions("hello @ world")
        assert result == []

    def test_multiple_distinct_mentions_preserved_in_order(self) -> None:
        """extract_mentions returns mentions in encounter order, no reordering.

        Regression guard: downstream consumers may rely on order for
        priority resolution (e.g., first @mention is the "primary" addressee).
        """
        result = extract_mentions("@Socrates and @Plato disagree")
        assert result == ["Socrates", "Plato"], (
            f"Expected ['Socrates', 'Plato'] in order, got {result!r}"
        )


# ===========================================================================
# TestIsMentionedCaseInsensitivity
# Regression guard for is_mentioned (thinker.py:88-117).
#
# The function lowercases both the mention and the thinker name before
# comparison, allowing "@socrates" to match thinker "Socrates" (and vice
# versa). Users naturally type @-mentions in lowercase, so removing the
# lowercase normalization would break the @mention feature for most users.
# ===========================================================================


class TestIsMentionedCaseInsensitivity:
    """Regression tests: is_mentioned is case-insensitive in both directions."""

    def test_lowercase_mention_matches_capitalized_thinker(self) -> None:
        """@socrates matches thinker 'Socrates' (mention lowercased).

        Regression guard: typing @socrates is the common case. If case
        sensitivity returned, users would have to type @Socrates exactly —
        and the @mention boost (0.98 prob) would silently fail for most.
        """
        assert is_mentioned("Tell me @socrates what is justice?", "Socrates") is True

    def test_uppercase_mention_matches_capitalized_thinker(self) -> None:
        """@SOCRATES matches thinker 'Socrates' (both folded to lower)."""
        assert is_mentioned("@SOCRATES tell me", "Socrates") is True

    def test_lowercase_first_name_matches_multi_word_thinker(self) -> None:
        """@marie matches 'Marie Curie' via first-name path, case-insensitive.

        Regression guard for the first_name_lower path in is_mentioned.
        Users typing @marie should get a response from "Marie Curie".
        """
        assert is_mentioned("@marie what is radioactivity?", "Marie Curie") is True


# ===========================================================================
# TestLanguageInstructionEnglishBypass
# Regression guard for _get_language_instruction (thinker.py:40-52).
#
# The early-return for English (`if language == "en": return ""`) is
# load-bearing: it prevents wasteful prompt suffixes like "IMPORTANT: Respond
# in English." from being appended to every English prompt. Removing this
# bypass would silently inflate prompt tokens by ~30 chars per request,
# adding measurable cost at scale.
# ===========================================================================


class TestLanguageInstructionEnglishBypass:
    """Regression tests: English language returns empty instruction (token saver)."""

    def test_english_returns_empty_string(self) -> None:
        """_get_language_instruction('en') returns '' (no prompt suffix).

        Regression guard: the early-return must be preserved. Otherwise
        every English prompt gets a redundant "Respond in English" line that
        costs tokens at scale.
        """
        assert _get_language_instruction("en") == ""

    def test_non_english_returns_non_empty_string(self) -> None:
        """Non-English languages return a non-empty 'Respond in X.' suffix.

        Regression guard: complements the English bypass. If a future refactor
        accidentally returned '' for all languages, every thinker prompt
        would lose its language directive and responses would default to
        English regardless of user preference.
        """
        for lang in ("es", "fr", "de", "hi"):
            instruction = _get_language_instruction(lang)
            assert instruction.startswith("\n\nIMPORTANT: Respond in "), (
                f"Language {lang!r} produced unexpected instruction: "
                f"{instruction!r}. The language prompt suffix has regressed."
            )
            assert instruction.endswith("."), (
                f"Language instruction for {lang!r} should end with period: {instruction!r}"
            )

    def test_unknown_language_falls_back_to_raw_code(self) -> None:
        """Unknown language uses the raw code as the language name.

        Regression guard: an unknown language code (e.g., 'xx') should NOT
        crash or return empty — it falls back to using the code itself in
        the instruction. This makes adding a new language a single
        LANGUAGE_NAMES dict entry (no code changes elsewhere).
        """
        instruction = _get_language_instruction("xx")
        # Doesn't crash, doesn't return empty (only "en" returns empty)
        assert instruction != ""
        assert "xx" in instruction


# ===========================================================================
# TestSplitBubblesEmptyAndShort
# Regression guard for _split_response_into_bubbles boundaries:
#   - empty input  → []          (line 698-699)
#   - short input  → [text]      (line 705)
#
# These boundary cases are easy to overlook in a refactor (e.g., a change to
# the strategy_roll logic could fall through to None or raise on empty input).
# The agent loop calls this function on every response, so a crash here
# would take down the entire conversation.
# ===========================================================================


class TestSplitBubblesEmptyAndShort:
    """Regression tests: _split_response_into_bubbles handles boundary inputs."""

    def test_empty_string_returns_empty_list(self) -> None:
        """_split_response_into_bubbles('') returns [], not [''] or None.

        Regression guard: the agent loop computes `cost_per_bubble = cost /
        len(bubbles) if bubbles else 0`. Returning `['']` would yield 1
        "empty" bubble and the broadcast would emit a blank message.
        """
        service = ThinkerService()
        assert service._split_response_into_bubbles("") == []

    def test_whitespace_only_returns_at_most_one_empty_bubble(self) -> None:
        """Whitespace-only response goes through the short-text branch.

        Documents current behavior: after .strip(), the input is '' which
        is shorter than 60 chars, so the function returns [''] via the
        short-text fast path (line 705) without applying the trailing
        empty-string filter that the long-text path uses.

        Regression guard: the agent loop checks `if response_text:` before
        calling this function, so empty bubbles never reach the broadcast
        in practice. This test pins down current behavior so a future
        cleanup that filters at the top level doesn't silently regress the
        short-text fast path.
        """
        service = ThinkerService()
        result = service._split_response_into_bubbles("   \n\t  ")
        # At most one bubble; if present, it's empty (post-strip)
        assert len(result) <= 1
        for b in result:
            assert b == "", f"Non-empty bubble from whitespace input: {b!r}"

    def test_short_text_returns_single_bubble(self) -> None:
        """Text shorter than 60 chars always returns one bubble.

        Regression guard for line 705: `if len(text) < 60: return [text]`.
        Removing this would force short messages through the splitting
        logic, potentially producing zero bubbles for borderline cases.
        """
        service = ThinkerService()
        short_text = "I agree completely with that point."  # 35 chars
        result = service._split_response_into_bubbles(short_text)
        assert result == [short_text], f"Short text should be a single bubble: {result!r}"

    def test_borderline_60_char_text_does_not_crash(self) -> None:
        """Text at exactly 60 chars (the boundary) returns at least one bubble.

        Regression guard: off-by-one at the `len(text) < 60` check would
        produce different behavior at exactly 60 chars. Test that both sides
        of the boundary return at least one non-empty bubble.
        """
        service = ThinkerService()
        text_59 = "A" * 59
        text_60 = "A" * 60
        text_61 = "A" * 61

        for text in (text_59, text_60, text_61):
            result = service._split_response_into_bubbles(text)
            assert len(result) >= 1, (
                f"Boundary text of length {len(text)} should produce "
                f"at least one bubble, got {result!r}"
            )
            assert all(b for b in result), "No bubble should be empty"
