"""Mental model data models for dynamic character psychological state.

Complete psychological state model covering:
- BigFiveProfile: 5-dimensional personality (Costa & McCrae, 1992)
- CognitiveDistortion: CBT distortion tendency weights (Beck, 1976)
- SomaticState: embodied perception (EFT-CoT, Du et al., 2026)
- QualitativeSuffering: irreversible trauma (Emotional Cost Functions)
- LinguisticStyle: decoupled expression patterns (TTM, Zhan et al., 2025)
- CharacterMind: stable identity (personality + cognition + language)
- EmotionalState: volatile per-event state (emotion + body + active distortion)
- NeedState: Maslow hierarchy tracking (Maslow, 1943)
- MentalState: composite of all layers
- EventImpact: LLM-generated impact from event analysis
"""

from enum import IntEnum, StrEnum, auto
from typing import TYPE_CHECKING, List, Optional

from fabricatio_core.models.generic import Base, ProposedAble
from pydantic import Field

if TYPE_CHECKING:
    from fabricatio_character.models.character import CharacterCard

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


# ── Enums ──


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

    common_pronouns: List[str] = Field(default_factory=list)
    """Preferred pronouns."""

    common_modals: List[str] = Field(default_factory=list)
    """Preferred modal verbs."""
    common_adjectives: List[str] = Field(default_factory=list)
    """Preferred adjectives and descriptors."""

    style_references: List[str] = Field(default_factory=list)
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


# ── Layer models ──


class CharacterMind(Base):
    """Stable psychological identity. Seeded once from CharacterCard, drifts slowly.

    Contains personality, cognitive tendencies, and linguistic style.
    Changes only through slow drift over many events.
    """

    character_name: str
    """Name of the character this mind belongs to."""

    personality: BigFiveProfile = Field(default_factory=BigFiveProfile)
    """Stable personality traits."""

    cognitive_tendencies: CognitiveDistortion = Field(default_factory=CognitiveDistortion)
    """Character's cognitive distortion tendency weights."""

    linguistic_style: LinguisticStyle = Field(default_factory=LinguisticStyle)
    """Decoupled language expression patterns."""


class EmotionalState(Base):
    """Volatile per-event emotional and physical state.

    Replaced (not mutated) every event. Contains the current emotion,
    its physical manifestation, and which cognitive distortion is active.
    """

    emotion: Emotion = Emotion.NEUTRAL
    """Current dominant emotion."""

    intensity: float = Field(ge=0, le=100, default=0.0)
    """Emotion intensity 0-100."""

    somatic: SomaticState = Field(default_factory=SomaticState)
    """Current body sensations."""

    active_distortion: Optional[Distortion] = None
    """Currently activated cognitive distortion (per-event, volatile)."""
    latest_situation: Optional["SituationProfile"] = None
    """DIAMONDS profile from the latest event (volatile, for prompt injection)."""


class NeedState(Base):
    """Maslow need hierarchy tracking. Accumulated over time."""

    current_level: MaslowLevel = MaslowLevel.PHYSIOLOGICAL
    """Current dominant need level."""

    satisfied: List[MaslowLevel] = Field(default_factory=list)
    """Already satisfied need levels."""

    counters: dict[MaslowLevel, int] = Field(default_factory=lambda: dict.fromkeys(MaslowLevel, 0))
    """Accumulated satisfaction events per level."""


# ── Composite state ──


class MentalState(Base):
    """Complete psychological state. All theories represented.

    Three layers:
    - mind: stable identity (personality, cognition, language)
    - emotion: volatile per-event state (emotion, body, active distortion)
    - needs: accumulated Maslow hierarchy
    Plus sufferings (permanent trauma history).
    """

    mind: CharacterMind
    """Stable psychological identity."""

    emotion: EmotionalState = Field(default_factory=EmotionalState)
    """Volatile per-event emotional state."""

    needs: NeedState = Field(default_factory=NeedState)
    """Maslow need hierarchy tracking."""

    sufferings: List[QualitativeSuffering] = Field(default_factory=list)
    """Accumulated irreversible traumas."""

    @classmethod
    def from_card(cls, card: "CharacterCard") -> "MentalState":
        """Seed MentalState from a CharacterCard with minimal defaults.

        Sets character name and default values. For intelligent seeding
        with LLM-driven need/distortion classification, use UseMind.seed_from().
        """
        return cls(
            mind=CharacterMind(character_name=card.name),
        )

    def drop_level(self, threatened: MaslowLevel) -> "MentalState":
        """Drop to or below the threatened need level."""
        self.needs.satisfied = [n for n in self.needs.satisfied if n < threatened]
        if threatened > MaslowLevel.PHYSIOLOGICAL:
            self.needs.current_level = min(self.needs.current_level, MaslowLevel(threatened - 1))
        else:
            self.needs.current_level = MaslowLevel.PHYSIOLOGICAL
        return self

    def accumulate_satisfaction(self, fulfilled: MaslowLevel) -> "MentalState":
        """Accumulate satisfaction count; rise level when threshold met."""
        from fabricatio_character.config import character_config

        self.needs.counters[fulfilled] = self.needs.counters.get(fulfilled, 0) + 1
        if self.needs.counters[fulfilled] >= character_config.mind_satisfaction_threshold:
            if fulfilled not in self.needs.satisfied:
                self.needs.satisfied.append(fulfilled)
            if self.needs.current_level < MaslowLevel.SELF_ACTUALIZATION:
                self.needs.current_level = MaslowLevel(self.needs.current_level + 1)
            self.needs.counters[fulfilled] = 0
        return self


# ── Event analysis output ──


class EventImpact(ProposedAble):
    """LLM-generated impact from event analysis.

    Contains all fields the LLM determines: emotion, personality drift,
    distortion activation, and need transitions.
    """

    emotion: Optional[Emotion] = None
    """Triggered emotion name."""

    emotion_intensity: float = Field(ge=0, le=100, default=0)
    """Emotion intensity 0-100."""

    personality_shift: dict[BigFiveDimension, float] = Field(default_factory=dict)
    """BigFive dimension deltas (e.g. {BigFiveDimension.NEUROTICISM: 5.0})."""

    triggers_distortion: Optional[Distortion] = None
    """Triggered cognitive distortion type."""

    threatens_need: Optional[MaslowLevel] = None
    """Need level threatened by the event."""

    fulfills_need: Optional[MaslowLevel] = None
    """Need level fulfilled by the event."""
    created_suffering: Optional["QualitativeSuffering"] = None
    """Suffering created from high-intensity emotional events."""

    situation: Optional["SituationProfile"] = None
    """DIAMONDS situation profile from event analysis."""


class DistortionAnalysis(ProposedAble):
    """CBT distortion analysis output — used by LLM distortion judgment path."""

    triggered_distortion: Optional[Distortion] = None
    internal_monologue: str = ""
    reasoning: str = ""


class EventContext(Base):
    """Typed context for event analysis template rendering."""

    event: str
    """The event text to analyze."""

    emotion: Emotion = Emotion.NEUTRAL
    """Current emotion."""

    emotion_intensity: float = 0.0
    """Emotion intensity 0-100."""

    current_need: MaslowLevel = MaslowLevel.PHYSIOLOGICAL
    """Current MaslowLevel."""

    def as_template_data(self) -> dict[str, str | float | bool | int]:
        """Convert to dict with string values for template rendering."""
        return {
            "event": self.event,
            "emotion": self.emotion.value,
            "emotion_intensity": f"{self.emotion_intensity:.0f}",
            "current_need": self.current_need.name,
        }


class SufferingSummary(Base):
    """Suffering entry for template rendering."""

    what_was_lost: str
    the_void: str
    how_it_changed_me: str


class AsPromptData(Base):
    """Typed data for system prompt template rendering."""

    personality_rules: list[str]
    need_description: str
    emotion: str
    emotion_intensity: str
    emotion_high: bool
    emotion_mid: bool
    cognitive_bias: str | None = None
    bias_example: str = ""
    has_somatic: bool = False
    somatic_heart_rate: str = "normal"
    somatic_breathing: str = "normal"
    somatic_muscle_tension: str = "relaxed"
    somatic_facial_expression: str = "neutral"
    somatic_voice: str = "steady"
    has_sufferings: bool = False
    sufferings: list[SufferingSummary] = Field(default_factory=list)
    has_linguistic: bool = False
    linguistic_preferences: str = ""
    linguistic_pronouns: list[str] | None = None
    linguistic_modals: list[str] | None = None
    has_situation: bool = False
    top_situation_dimension: str = ""
    situation_adversity: float = 0.0
    situation_negativity: float = 0.0

    def as_template_data(self) -> dict[str, str | float | bool | int | list | None]:
        """Convert to dict for TEMPLATE_MANAGER.render_template()."""
        return self.model_dump()
