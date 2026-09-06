"""Mental model data models for dynamic character psychological state.

Layered composite:
- CharacterMind: stable identity (personality + cognition + language + age)
- EmotionalState: volatile per-event state (emotion + body + active distortion)
- NeedState: Maslow hierarchy tracking (Maslow, 1943)
- MentalState: the self-sufficient composite. Owns rule application
  (:meth:`MentalState.apply`), prompt rendering (:class:`AsPrompt` protocol),
  and persistence (:class:`PersistentAble`) — same conventions as
  CharacterCard. Seed it via :meth:`MentalState.from_card` (no LLM) or
  ``UseMind.seed_from(card)`` (LLM-judged).
- EventImpact: LLM-generated impact from event analysis
- EventContext / SufferingSummary / AsPromptData: typed template payloads

Vocabulary and primitive trait models (domain enums, BigFiveProfile,
CognitiveDistortion, SomaticState, QualitativeSuffering, LinguisticStyle) live
in :mod:`fabricatio_character.models.psych` and are re-exported here, so
``fabricatio_character.models.mental`` remains the single public import
surface.
"""

from typing import TYPE_CHECKING, Any, ClassVar, Self

from fabricatio_capabilities.models.generic import AsPrompt, PersistentAble
from fabricatio_core.models.generic import Base, ProposedAble
from pydantic import Field

from fabricatio_character.config import character_config
from fabricatio_character.models.psych import (
    BigFiveDimension,
    BigFiveProfile,
    Breathing,
    CognitiveDistortion,
    Distortion,
    Emotion,
    FacialExpression,
    HeartRate,
    LinguisticStyle,
    MaslowLevel,
    MuscleTension,
    PersonalityFlag,
    QualitativeSuffering,
    SituationDimension,
    SituationProfile,
    SomaticState,
    VoiceQuality,
)

if TYPE_CHECKING:
    from fabricatio_character.models.character import CharacterCard

# ── Layer models ──


class CharacterMind(Base):
    """Stable psychological identity. Seeded once from CharacterCard, drifts slowly.

    Contains personality, cognitive tendencies, linguistic style, and age.
    Changes only through slow drift over many events.
    """

    character_name: str
    """Name of the character this mind belongs to."""

    age: int = Field(ge=0, default=25)
    """Character age. Scales personality drift per event (see ``age_shift_scale``)."""

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

    active_distortion: Distortion | None = None
    """Currently activated cognitive distortion (per-event, volatile)."""

    latest_situation: SituationProfile | None = None
    """DIAMONDS profile from the latest event (volatile, for prompt injection)."""


class NeedState(Base):
    """Maslow need hierarchy tracking. Accumulated over time."""

    current_level: MaslowLevel = MaslowLevel.PHYSIOLOGICAL
    """Current dominant need level."""

    satisfied: list[MaslowLevel] = Field(default_factory=list)
    """Already satisfied need levels."""

    counters: dict[MaslowLevel, int] = Field(default_factory=lambda: dict.fromkeys(MaslowLevel, 0))
    """Accumulated satisfaction events per level."""


# ── Composite state ──


class MentalState(AsPrompt, PersistentAble):
    """Complete psychological state. All theories represented.

    Three layers:
    - mind: stable identity (personality, cognition, language, age)
    - emotion: volatile per-event state (emotion, body, active distortion)
    - needs: accumulated Maslow hierarchy
    Plus sufferings (permanent trauma history).

    Self-sufficient: rule application (:meth:`apply`), prompt rendering
    (:meth:`as_prompt`, AsPrompt protocol), and persistence
    (:class:`PersistentAble`) live on the model, mirroring CharacterCard.
    Immutable-update style: :meth:`apply` returns a new instance.
    """

    rendering_template: ClassVar[str] = character_config.mind_system_prompt_template
    """Handlebars template used by :meth:`as_prompt`."""

    mind: CharacterMind
    """Stable psychological identity."""

    emotion: EmotionalState = Field(default_factory=EmotionalState)
    """Volatile per-event emotional state."""

    needs: NeedState = Field(default_factory=NeedState)
    """Maslow need hierarchy tracking."""

    sufferings: list[QualitativeSuffering] = Field(default_factory=list)
    """Accumulated irreversible traumas."""

    @classmethod
    def from_card(cls, card: "CharacterCard", age: int = 25) -> "MentalState":
        """Seed MentalState from a CharacterCard with minimal defaults.

        Bridges the card's free-text ``mood`` into an :class:`Emotion` when it
        names one exactly (case-insensitive). For LLM-judged seeding of the
        initial need level and cognitive distortions, use
        ``UseMind.seed_from(card)`` instead.
        """
        try:
            emotion = Emotion(card.mood.strip().lower())
        except ValueError:
            emotion = Emotion.NEUTRAL
        return cls(
            mind=CharacterMind(character_name=card.name, age=age),
            emotion=EmotionalState(emotion=emotion),
        )

    def apply(self, impact: "EventImpact") -> Self:
        """Apply deterministic rules to evolve this state from an event impact.

        Returns a NEW MentalState (copy-on-write; this instance is untouched).

        Rule order: need threat drop / satisfaction accumulation, age-scaled
        personality drift (age read from ``self.mind.age``), suffering
        accumulation, situation storage, emotional state replacement.
        """
        new_state = self.model_copy(deep=True)

        # 1. Need transitions
        if impact.threatens_need is not None:
            new_state = new_state.drop_level(impact.threatens_need)
        if impact.fulfills_need is not None:
            new_state = new_state.accumulate_satisfaction(impact.fulfills_need)

        # 2. Personality drift (age-scaled from this mind's own age)
        scale = character_config.age_shift_scale(new_state.mind.age)
        new_state.mind.personality = new_state.mind.personality.shifted(impact.personality_shift, scale=scale)

        # 3. Suffering accumulation
        if impact.created_suffering is not None:
            new_state.sufferings.append(impact.created_suffering)

        # 4. Situation storage (independent of emotion — always apply if present)
        if impact.situation is not None:
            new_state.emotion.latest_situation = impact.situation

        # 5. Emotional state (replace, not mutate)
        if impact.emotion is not None:
            new_state.emotion = EmotionalState(
                emotion=impact.emotion,
                intensity=impact.emotion_intensity,
                somatic=SomaticState.from_emotion(impact.emotion, impact.emotion_intensity),
                active_distortion=impact.triggers_distortion,
                latest_situation=impact.situation or new_state.emotion.latest_situation,
            )

        return new_state

    def drop_level(self, threatened: MaslowLevel) -> Self:
        """Drop to or below the threatened need level."""
        self.needs.satisfied = [n for n in self.needs.satisfied if n < threatened]
        if threatened > MaslowLevel.PHYSIOLOGICAL:
            self.needs.current_level = min(self.needs.current_level, MaslowLevel(threatened - 1))
        else:
            self.needs.current_level = MaslowLevel.PHYSIOLOGICAL
        return self

    def accumulate_satisfaction(self, fulfilled: MaslowLevel) -> Self:
        """Accumulate satisfaction count; rise level when threshold met."""
        self.needs.counters[fulfilled] = self.needs.counters.get(fulfilled, 0) + 1
        if self.needs.counters[fulfilled] >= character_config.mind_satisfaction_threshold:
            if fulfilled not in self.needs.satisfied:
                self.needs.satisfied.append(fulfilled)
            if self.needs.current_level < MaslowLevel.SELF_ACTUALIZATION:
                self.needs.current_level = MaslowLevel(self.needs.current_level + 1)
            self.needs.counters[fulfilled] = 0
        return self

    def _as_prompt_inner(self) -> dict[str, Any]:
        """Assemble the typed template payload for ``mind_system_prompt``."""
        p = self.mind.personality
        s = self.emotion.somatic
        ls = self.mind.linguistic_style

        active_distortion = self.emotion.active_distortion

        data = AsPromptData(
            personality_rules=[
                desc for key, desc in character_config.mind_personality_rules.items() if p.personality_flag(key)
            ],
            need_description=character_config.mind_need_focus.get(self.needs.current_level, ""),
            emotion=self.emotion.emotion.value,
            emotion_intensity=f"{self.emotion.intensity:.0f}",
            emotion_high=self.emotion.intensity > character_config.mind_emotion_intensity_high,
            emotion_mid=self.emotion.intensity > character_config.mind_emotion_intensity_mid,
            cognitive_bias=active_distortion.value if active_distortion else None,
            bias_example=character_config.mind_bias_examples.get(active_distortion, "") if active_distortion else "",
            has_somatic=s.heart_rate != HeartRate.NORMAL or s.muscle_tension != MuscleTension.RELAXED,
            somatic_heart_rate=s.heart_rate.value,
            somatic_breathing=s.breathing.value,
            somatic_muscle_tension=s.muscle_tension.value,
            somatic_facial_expression=s.facial_expression.value,
            somatic_voice=s.voice.value,
            has_sufferings=bool(self.sufferings),
            sufferings=[
                SufferingSummary(
                    what_was_lost=sv.what_was_lost,
                    the_void=sv.the_void,
                    how_it_changed_me=sv.how_it_changed_me,
                )
                for sv in self.sufferings
            ],
            has_linguistic=bool(ls.preferences),
            linguistic_preferences=ls.preferences,
            linguistic_pronouns=ls.common_pronouns or None,
            linguistic_modals=ls.common_modals or None,
            has_situation=self.emotion.latest_situation is not None,
            top_situation_dimension=(
                self.emotion.latest_situation.top_dimension().value if self.emotion.latest_situation else ""
            ),
            situation_adversity=(self.emotion.latest_situation.adversity if self.emotion.latest_situation else 0.0),
            situation_negativity=(self.emotion.latest_situation.negativity if self.emotion.latest_situation else 0.0),
        )
        return data.as_template_data()


# ── Event analysis output ──


class EventImpact(ProposedAble):
    """LLM-generated impact from event analysis.

    Contains all fields the LLM determines: emotion, personality drift,
    distortion activation, and need transitions.
    """

    emotion: Emotion | None = None
    """Triggered emotion name."""

    emotion_intensity: float = Field(ge=0, le=100, default=0)
    """Emotion intensity 0-100."""

    personality_shift: dict[BigFiveDimension, float] = Field(default_factory=dict)
    """BigFive dimension deltas (e.g. {BigFiveDimension.NEUROTICISM: 5.0})."""

    triggers_distortion: Distortion | None = None
    """Triggered cognitive distortion type."""

    threatens_need: MaslowLevel | None = None
    """Need level threatened by the event."""

    fulfills_need: MaslowLevel | None = None
    """Need level fulfilled by the event."""

    created_suffering: QualitativeSuffering | None = None
    """Suffering created from high-intensity emotional events."""

    situation: SituationProfile | None = None
    """DIAMONDS situation profile from event analysis."""


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

    def as_template_data(self) -> dict[str, str | float | bool | int | list[Any] | None]:
        """Convert to dict for TEMPLATE_MANAGER.render_template()."""
        return self.model_dump()


__all__ = [
    "AsPromptData",
    "BigFiveDimension",
    "BigFiveProfile",
    "Breathing",
    "CharacterMind",
    "CognitiveDistortion",
    "Distortion",
    "Emotion",
    "EmotionalState",
    "EventContext",
    "EventImpact",
    "FacialExpression",
    "HeartRate",
    "LinguisticStyle",
    "MaslowLevel",
    "MentalState",
    "MuscleTension",
    "NeedState",
    "PersonalityFlag",
    "QualitativeSuffering",
    "SituationDimension",
    "SituationProfile",
    "SomaticState",
    "SufferingSummary",
    "VoiceQuality",
]
