"""Psychological vocabulary and primitive trait models.

Holds the enums and leaf models that ``config.py`` needs for its typed tables
(emotion-somatic map, distortion boosts, personality rules). This module MUST
NOT import :mod:`fabricatio_character.config` at module level — the config
singleton imports these types to declare its fields, so the dependency only
runs one way. Methods that need config values import it inside the function
body.

Contents:
- Emotion / Distortion / PersonalityFlag / MaslowLevel / BigFiveDimension /
  SituationDimension: domain enums
- SituationProfile: DIAMONDS 8-dim situational classification (Rauthmann et al., 2014)
- BigFiveProfile: 5-dimensional personality (Costa & McCrae, 1992)
- CognitiveDistortion: CBT distortion tendency weights (Beck, 1976)
- SomaticState: embodied perception enums + model (EFT-CoT, Du et al., 2026)
- QualitativeSuffering: irreversible trauma (Emotional Cost Functions)
- LinguisticStyle: decoupled expression patterns (TTM, Zhan et al., 2025)
"""

from enum import IntEnum, StrEnum, auto

from fabricatio_core.models.generic import Base, ProposedAble
from pydantic import Field

# -- Domain enums --


class Emotion(StrEnum):
    """Recognized emotion types."""

    NEUTRAL = auto()
    FEAR = auto()
    ANXIETY = auto()
    ANGER = auto()
    RAGE = auto()
    SADNESS = auto()
    GRIEF = auto()
    JOY = auto()
    HAPPINESS = auto()
    DISGUST = auto()
    CONTEMPT = auto()


class Distortion(StrEnum):
    """Cognitive distortion types from CBT framework."""

    CATASTROPHIZING = auto()
    BLACK_AND_WHITE = auto()
    PERSONALIZATION = auto()
    EMOTIONAL_REASONING = auto()
    SHOULD_THINKING = auto()


class PersonalityFlag(StrEnum):
    """Personality trait condition flags for prompt injection."""

    HIGH_NEUROTICISM = auto()
    LOW_AGREEABLENESS = auto()
    HIGH_EXTRAVERSION = auto()
    LOW_EXTRAVERSION = auto()
    HIGH_CONSCIENTIOUSNESS = auto()
    HIGH_OPENNESS = auto()


class MaslowLevel(IntEnum):
    """Maslow's hierarchy of needs. Higher value = higher need."""

    PHYSIOLOGICAL = auto()
    SAFETY = auto()
    BELONGING = auto()
    ESTEEM = auto()
    SELF_ACTUALIZATION = auto()


class BigFiveDimension(StrEnum):
    """Big Five personality dimension names."""

    OPENNESS = auto()
    CONSCIENTIOUSNESS = auto()
    EXTRAVERSION = auto()
    AGREEABLENESS = auto()
    NEUROTICISM = auto()


class SituationDimension(StrEnum):
    """DIAMONDS situational dimensions (Rauthmann et al., 2014)."""

    DUTY = auto()
    INTELLECT = auto()
    ADVERSITY = auto()
    MATING = auto()
    POSITIVITY = auto()
    NEGATIVITY = auto()
    DECEPTION = auto()
    SOCIALITY = auto()


class SituationProfile(ProposedAble):
    """8-dimensional situational classification per event.

    Each dimension scored 0.0-1.0 by LLM extraction.
    """

    duty: float = Field(ge=0, le=1, default=0)
    intellect: float = Field(ge=0, le=1, default=0)
    adversity: float = Field(ge=0, le=1, default=0)
    mating: float = Field(ge=0, le=1, default=0)
    positivity: float = Field(ge=0, le=1, default=0)
    negativity: float = Field(ge=0, le=1, default=0)
    deception: float = Field(ge=0, le=1, default=0)
    sociality: float = Field(ge=0, le=1, default=0)

    def as_vector(self) -> list[float]:
        """Return a flat vector of all 8 situation dimension scores."""
        return [
            self.duty,
            self.intellect,
            self.adversity,
            self.mating,
            self.positivity,
            self.negativity,
            self.deception,
            self.sociality,
        ]

    def top_dimension(self) -> SituationDimension:
        """Return the highest-scoring SituationDimension."""
        dims = list(SituationDimension)
        vals = self.as_vector()
        return dims[vals.index(max(vals))]


# ── Stable identity components ──


class BigFiveProfile(Base):
    """Big Five personality traits. Each dimension 0-100."""

    openness: float = Field(ge=0, le=100, default=50.0)
    """Curiosity vs practicality."""

    conscientiousness: float = Field(ge=0, le=100, default=50.0)
    """Self-discipline vs flexibility."""

    extraversion: float = Field(ge=0, le=100, default=50.0)
    """Outgoing vs reserved."""

    agreeableness: float = Field(ge=0, le=100, default=50.0)
    """Cooperative vs competitive."""

    neuroticism: float = Field(ge=0, le=100, default=50.0)
    """Anxious vs emotionally stable."""

    def as_vector(self) -> list[float]:
        """Return personality as a 5D vector [O, C, E, A, N]."""
        return [self.openness, self.conscientiousness, self.extraversion, self.agreeableness, self.neuroticism]

    def distance_to(self, other: "BigFiveProfile") -> float:
        """Euclidean distance between two personality profiles."""
        from math import sqrt

        return sqrt(sum((a - b) ** 2 for a, b in zip(self.as_vector(), other.as_vector(), strict=True)))

    def personality_flag(self, flag: "PersonalityFlag") -> bool:
        """Check a personality condition flag against this profile."""
        from fabricatio_character.config import character_config

        high = character_config.mind_personality_high
        low = character_config.mind_personality_low
        flag_map = {
            PersonalityFlag.HIGH_NEUROTICISM: self.neuroticism > high,
            PersonalityFlag.LOW_AGREEABLENESS: self.agreeableness < low,
            PersonalityFlag.HIGH_EXTRAVERSION: self.extraversion > high,
            PersonalityFlag.LOW_EXTRAVERSION: self.extraversion < low,
            PersonalityFlag.HIGH_CONSCIENTIOUSNESS: self.conscientiousness > high,
            PersonalityFlag.HIGH_OPENNESS: self.openness > high,
        }
        return flag_map.get(flag, False)


class CognitiveDistortion(Base):
    """CBT cognitive distortion tendency weights for a character."""

    catastrophizing: float = Field(ge=0, le=100, default=20.0)
    """Amplify threat."""

    black_and_white: float = Field(ge=0, le=100, default=20.0)
    """No middle ground."""

    personalization: float = Field(ge=0, le=100, default=20.0)
    """Self-blame."""

    emotional_reasoning: float = Field(ge=0, le=100, default=20.0)
    """Feelings = facts."""

    should_thinking: float = Field(ge=0, le=100, default=20.0)
    """Rigid expectations."""

    def top(self, n: int = 1) -> list["Distortion"]:
        """Return top-N most likely distortion types."""
        scores: dict[str, float] = self.model_dump()
        return [Distortion(k) for k in sorted(scores, key=scores.get, reverse=True)[:n]]

    def rule_filter(self, situation: "SituationProfile") -> dict[str, float]:
        """Compute distortion scores boosted by DIAMONDS situational dimensions.

        Base = character tendency weight. Boost = dim_score * boost_value from config.
        Returns dict with Distortion enum value strings as keys.
        """
        from fabricatio_character.config import character_config

        scores: dict[str, float] = self.model_dump()
        for dim_enum, distortion_boosts in character_config.mind_diamonds_distortion_boost.items():
            dim_score = getattr(situation, dim_enum.value, 0.0)
            if dim_score > 0:
                for distortion, boost in distortion_boosts.items():
                    key = distortion.value
                    scores[key] = scores.get(key, 0.0) + dim_score * boost
        return scores


class LinguisticStyle(ProposedAble):
    """Decoupled language expression patterns. Extracted from character dialogues."""

    preferences: str = ""
    """Natural language description of style tendencies."""

    common_pronouns: list[str] = Field(default_factory=list)
    """Preferred pronouns."""

    common_modals: list[str] = Field(default_factory=list)
    """Preferred modal verbs."""

    common_adjectives: list[str] = Field(default_factory=list)
    """Preferred adjectives and descriptors."""

    style_references: list[str] = Field(default_factory=list)
    """Exemplary utterances from the character for style reference."""


# -- Volatile components --


class HeartRate(StrEnum):
    """Heart rate states."""

    NORMAL = auto()
    ELEVATED = auto()
    RACING = auto()


class Breathing(StrEnum):
    """Breathing patterns."""

    NORMAL = auto()
    SLOW = auto()
    SHALLOW = auto()
    RAPID = auto()


class MuscleTension(StrEnum):
    """Muscle tension levels."""

    RELAXED = auto()
    TENSE = auto()
    RIGID = auto()
    TREMBLING = auto()


class FacialExpression(StrEnum):
    """Facial expression states."""

    NEUTRAL = auto()
    FROWN = auto()
    WIDE_EYES = auto()
    BLUSH = auto()


class VoiceQuality(StrEnum):
    """Voice quality states."""

    STEADY = auto()
    TREMBLING = auto()
    FAST = auto()
    QUIET = auto()


class SomaticState(Base):
    """Body sensations derived from emotion type and intensity."""

    heart_rate: HeartRate = HeartRate.NORMAL
    """Heart rate state."""

    breathing: Breathing = Breathing.NORMAL
    """Breathing pattern."""

    muscle_tension: MuscleTension = MuscleTension.RELAXED
    """Muscle tension level."""

    facial_expression: FacialExpression = FacialExpression.NEUTRAL
    """Facial expression."""

    voice: VoiceQuality = VoiceQuality.STEADY
    """Voice quality."""

    @classmethod
    def from_emotion(cls, emotion: "Emotion", intensity: float) -> "SomaticState":
        """Create SomaticState from emotion type and intensity via config mapping."""
        from fabricatio_character.config import character_config

        entry = character_config.mind_emotion_somatic_map.get(emotion)
        if entry is None:
            return cls()
        high_state, low_state = entry
        return high_state if intensity > character_config.mind_emotion_intensity_high else low_state


# ── Accumulated ──


class QualitativeSuffering(ProposedAble):
    """Irreversible trauma that permanently reshapes character."""

    what_was_lost: str
    """What was taken from the character."""

    the_void: str
    """The gap it created."""

    how_it_changed_me: str
    """How it reshaped the character."""

    anticipatory_dread: float = Field(ge=0, le=100, default=50.0)
    """Fear of similar situations (0-100)."""
