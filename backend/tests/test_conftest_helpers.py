"""Unit tests for shared conftest test helpers.

Test refactoring focus (Friday QA). The shared helpers in ``tests/conftest.py``
are used by hundreds of tests but have historically had no direct coverage of
their own. These tests pin down the contract of the pure (non-fixture) helpers
so future refactors of conftest cannot silently change their behavior.
"""

from tests.conftest import (
    bearer_header,
    create_mock_thinker_profile,
    create_mock_thinker_suggestion_json,
    create_thinker_input,
    make_simple_thinker_list,
)


class TestBearerHeader:
    """Contract for the bearer_header() Authorization-header builder."""

    def test_token_string_produces_bearer_header(self) -> None:
        """A raw token string is wrapped as ``Authorization: Bearer <token>``."""
        assert bearer_header("abc123") == {"Authorization": "Bearer abc123"}

    def test_auth_dict_extracts_access_token(self) -> None:
        """A dict with an access_token key is unwrapped to the token value."""
        data = {"access_token": "xyz789", "user": {"id": "u1"}}
        assert bearer_header(data) == {"Authorization": "Bearer xyz789"}

    def test_dict_and_token_forms_are_equivalent(self) -> None:
        """Passing the dict or its access_token yields the same header."""
        data = {"access_token": "same-token"}
        assert bearer_header(data) == bearer_header(data["access_token"])

    def test_returns_fresh_dict_each_call(self) -> None:
        """Each call returns an independent dict (safe to mutate per-test)."""
        first = bearer_header("t")
        second = bearer_header("t")
        assert first == second
        assert first is not second
        first["Authorization"] = "mutated"
        assert second["Authorization"] == "Bearer t"

    def test_only_authorization_key_present(self) -> None:
        """The header dict contains exactly one key: Authorization."""
        assert list(bearer_header("t").keys()) == ["Authorization"]


class TestMakeSimpleThinkerList:
    """Contract for the make_simple_thinker_list() placeholder builder."""

    def test_defaults_match_documented_placeholder(self) -> None:
        """Default values are the documented 'Thinker'/'Bio'/... placeholders."""
        result = make_simple_thinker_list()
        assert result == [
            {"name": "Thinker", "bio": "Bio", "positions": "Positions", "style": "Style"}
        ]

    def test_returns_single_element_list(self) -> None:
        """The helper always returns a one-element list."""
        assert len(make_simple_thinker_list("Plato")) == 1

    def test_custom_name_overrides_only_name(self) -> None:
        """Overriding the name leaves the other placeholder fields intact."""
        result = make_simple_thinker_list("Kant")
        assert result[0]["name"] == "Kant"
        assert result[0]["bio"] == "Bio"


class TestCreateThinkerInput:
    """Contract for the create_thinker_input() request-body builder."""

    def test_defaults_derive_fields_from_name(self) -> None:
        """Unspecified fields are derived from the thinker name."""
        result = create_thinker_input("Hume")
        assert result == {
            "name": "Hume",
            "bio": "Bio of Hume",
            "positions": "Positions of Hume",
            "style": "Style of Hume",
        }

    def test_explicit_fields_take_precedence(self) -> None:
        """Explicitly provided fields override the name-derived defaults."""
        result = create_thinker_input("Descartes", bio="Cogito", style="Meditative")
        assert result["bio"] == "Cogito"
        assert result["style"] == "Meditative"
        # Unspecified field still derives from name
        assert result["positions"] == "Positions of Descartes"

    def test_positions_accepts_list(self) -> None:
        """Positions may be supplied as a list and is passed through unchanged."""
        positions = ["Rationalism", "Dualism"]
        result = create_thinker_input("Spinoza", positions=positions)
        assert result["positions"] == positions


class TestCreateMockThinkerProfile:
    """Contract for create_mock_thinker_profile()."""

    def test_defaults_derive_from_name(self) -> None:
        """Missing fields are derived from the name."""
        profile = create_mock_thinker_profile("Aristotle")
        assert profile["bio"] == "Bio of Aristotle"
        assert profile["positions"] == "Positions of Aristotle"
        assert profile["style"] == "Style of Aristotle"

    def test_overrides_respected(self) -> None:
        """Explicit values override name-derived defaults."""
        profile = create_mock_thinker_profile("Locke", bio="Empiricist")
        assert profile["bio"] == "Empiricist"


class TestCreateMockThinkerSuggestionJson:
    """Contract for create_mock_thinker_suggestion_json()."""

    def test_produces_parseable_suggestion_payload(self) -> None:
        """Output is valid JSON shaped as a suggest_thinkers response."""
        import json

        payload = json.loads(create_mock_thinker_suggestion_json("Nietzsche"))
        assert isinstance(payload, list)
        assert payload[0]["name"] == "Nietzsche"
        # Nested profile carries the same name plus derived defaults
        assert payload[0]["profile"]["name"] == "Nietzsche"
        assert payload[0]["profile"]["bio"] == "Bio of Nietzsche"

    def test_custom_reason_included(self) -> None:
        """A custom reason is reflected in the serialized payload."""
        import json

        payload = json.loads(create_mock_thinker_suggestion_json("Marx", reason="Economic theory"))
        assert payload[0]["reason"] == "Economic theory"
