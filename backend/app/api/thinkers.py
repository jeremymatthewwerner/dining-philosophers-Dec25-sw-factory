"""API routes for thinker suggestions and validation."""

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.exceptions import ThinkerAPIError
from app.schemas import (
    ThinkerProfile,
    ThinkerSuggestion,
    ThinkerSuggestRequest,
    ThinkerValidateRequest,
    ThinkerValidateResponse,
)

router = APIRouter()

# Mock data for development without API key
MOCK_THINKERS: dict[str, ThinkerProfile] = {
    "socrates": ThinkerProfile(
        name="Socrates",
        bio="Ancient Greek philosopher from Athens (470-399 BC). Founder of Western philosophy.",
        positions="Known for the Socratic method of questioning, belief that wisdom begins with acknowledging ignorance.",
        style="Uses probing questions to examine beliefs. Humble yet persistent. Often claims to know nothing.",
    ),
    "aristotle": ThinkerProfile(
        name="Aristotle",
        bio="Ancient Greek philosopher (384-322 BC). Student of Plato, tutor to Alexander the Great.",
        positions="Virtue ethics, empiricism, logic. Believed in finding the golden mean between extremes.",
        style="Systematic and methodical. Builds arguments step by step. Favors observation and classification.",
    ),
    "marie curie": ThinkerProfile(
        name="Marie Curie",
        bio="Polish-French physicist and chemist (1867-1934). First woman to win a Nobel Prize.",
        positions="Pioneer in radioactivity research. Advocate for women in science.",
        style="Precise and methodical. Deeply passionate about scientific inquiry. Modest about achievements.",
    ),
    "albert einstein": ThinkerProfile(
        name="Albert Einstein",
        bio="German-born theoretical physicist (1879-1955). Developed the theory of relativity.",
        positions="Believed in the beauty and simplicity of nature's laws. Pacifist and humanitarian.",
        style="Uses vivid thought experiments. Playful yet profound. Often uses analogies and metaphors.",
    ),
    "maya angelou": ThinkerProfile(
        name="Maya Angelou",
        bio="American poet, memoirist, and civil rights activist (1928-2014).",
        positions="Champion of human dignity, civil rights, and the power of storytelling.",
        style="Eloquent and poetic. Draws from personal experience. Warm yet commanding presence.",
    ),
    "confucius": ThinkerProfile(
        name="Confucius",
        bio="Chinese philosopher and politician (551-479 BC). Founder of Confucianism.",
        positions="Emphasis on moral virtue, proper conduct, filial piety, and social harmony.",
        style="Uses aphorisms and parables. Values tradition and ritual. Teacher-like demeanor.",
    ),
}


async def get_mock_suggestions(_topic: str, count: int) -> list[ThinkerSuggestion]:
    """Get mock thinker suggestions for development with Wikipedia images."""
    import asyncio

    from app.services.thinker import thinker_service

    base_suggestions = [
        ("Socrates", "socrates", "Master of questioning and examining fundamental assumptions."),
        (
            "Albert Einstein",
            "albert einstein",
            "Brilliant at connecting abstract concepts to real-world understanding.",
        ),
        (
            "Maya Angelou",
            "maya angelou",
            "Brings wisdom from lived experience and artistic expression.",
        ),
        (
            "Aristotle",
            "aristotle",
            "Systematic thinker who categorizes and builds logical frameworks.",
        ),
        (
            "Marie Curie",
            "marie curie",
            "Represents empirical science and perseverance in discovery.",
        ),
    ]

    # Fetch Wikipedia images in parallel for performance
    selected = base_suggestions[:count]
    image_tasks = [thinker_service.get_wikipedia_image(name) for name, _, _ in selected]
    images = await asyncio.gather(*image_tasks, return_exceptions=True)

    suggestions = []
    for (name, key, reason), image in zip(selected, images, strict=False):
        profile = MOCK_THINKERS[key]
        image_url = image if isinstance(image, str) else None
        profile_with_image = ThinkerProfile(
            name=profile.name,
            bio=profile.bio,
            positions=profile.positions,
            style=profile.style,
            image_url=image_url,
        )
        suggestions.append(
            ThinkerSuggestion(
                name=name,
                reason=reason,
                profile=profile_with_image,
            )
        )
    return suggestions


@router.post("/suggest", response_model=list[ThinkerSuggestion])
async def suggest_thinkers(
    data: ThinkerSuggestRequest,
) -> list[ThinkerSuggestion]:
    """Get thinker suggestions for a topic.

    Uses Claude API if configured, otherwise returns mock suggestions.
    """
    from app.services.thinker import thinker_service

    settings = get_settings()

    if not settings.anthropic_api_key:
        # Return mock suggestions for development
        return await get_mock_suggestions(data.topic, data.count)

    # Use the thinker service to get real suggestions
    try:
        suggestions = await thinker_service.suggest_thinkers(data.topic, data.count, data.exclude)
        if suggestions:
            return suggestions
    except ThinkerAPIError as e:
        # Return HTTP error with the API error message
        status_code = 503 if e.is_quota_error else 502
        raise HTTPException(status_code=status_code, detail=e.message) from e

    # Fallback to mock suggestions if API call fails (but not due to quota)
    return await get_mock_suggestions(data.topic, data.count)


@router.post("/validate", response_model=ThinkerValidateResponse)
async def validate_thinker(
    data: ThinkerValidateRequest,
) -> ThinkerValidateResponse:
    """Validate that a thinker name refers to a real person.

    Uses Claude API if configured, otherwise uses mock validation.
    """
    from app.services.thinker import thinker_service

    settings = get_settings()
    name_lower = data.name.lower()

    # Check mock thinkers (for names and bios), but always fetch Wikipedia image
    if name_lower in MOCK_THINKERS:
        profile = MOCK_THINKERS[name_lower]
        # Fetch Wikipedia image for the thinker
        image_url = await thinker_service.get_wikipedia_image(profile.name)
        profile_with_image = ThinkerProfile(
            name=profile.name,
            bio=profile.bio,
            positions=profile.positions,
            style=profile.style,
            image_url=image_url,
        )
        return ThinkerValidateResponse(
            valid=True,
            name=profile.name,
            profile=profile_with_image,
        )

    if not settings.anthropic_api_key:
        # In development without API key, only accept mock thinkers
        return ThinkerValidateResponse(
            valid=False,
            name=data.name,
            error=f"Unknown thinker: {data.name}. Try one of: Socrates, Aristotle, Marie Curie, Albert Einstein, Maya Angelou, Confucius",
        )

    # Use the thinker service to validate
    try:
        is_valid, maybe_profile = await thinker_service.validate_thinker(data.name)
        if is_valid and maybe_profile:
            profile = maybe_profile
            return ThinkerValidateResponse(
                valid=True,
                name=profile.name,
                profile=profile,
            )
    except ThinkerAPIError as e:
        # Return HTTP error with the API error message
        status_code = 503 if e.is_quota_error else 502
        raise HTTPException(status_code=status_code, detail=e.message) from e

    return ThinkerValidateResponse(
        valid=False,
        name=data.name,
        error=f"Could not validate '{data.name}' as a real historical or contemporary figure",
    )
