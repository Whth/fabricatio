"""Utilities for character cards."""

from fabricatio_character.models.character import CharacterCard
from fabricatio_character.models.mental import Distortion


def dump_card(*card: CharacterCard) -> str:
    """Dump character cards."""
    return "\n".join(c.as_prompt() for c in card)


# -- CBT cognitive distortion helpers --


def top_with_confidence(
    scores: dict[str, float],
) -> tuple[Distortion | None, float]:
    """Return (top_distortion, confidence_score). None if all zero.

    Args:
        scores: Dict with Distortion enum value strings as keys, scores as values.

    Returns:
        Tuple of (top distortion or None, confidence score).
    """
    if not scores or max(scores.values()) == 0:
        return None, 0.0
    top = max(scores, key=scores.__getitem__)
    return Distortion(top), scores[top]


def is_high_confidence(confidence: float) -> bool:
    """Check if confidence score exceeds the CBT threshold from config."""
    from fabricatio_character.config import character_config

    return confidence > character_config.mind_cbt_confidence_threshold
