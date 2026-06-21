"""Configuration for fabricatio-character.

Single CharacterConfig with all tuneable parameters: templates, thresholds,
psychological knowledge prose, seed heuristics, and emotion-somatic mapping.

Usage:
    from fabricatio_character.config import character_config
    value = character_config.mind_personality_high
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple

from fabricatio_core import CONFIG

from fabricatio_character.models.mental import (
    Breathing,
    Distortion,
    Emotion,
    FacialExpression,
    HeartRate,
    MaslowLevel,
    MuscleTension,
    PersonalityFlag,
    SomaticState,
    VoiceQuality,
)


@dataclass(frozen=True)
class CharacterConfig:
    """Configuration for fabricatio-character."""

    # ── Character card template ──
    render_character_card_template: str = "built-in/render_character_card"
    """Template to use for rendering character cards."""

    # ── Mind system templates (resolved by TEMPLATE_MANAGER) ──
    mind_system_prompt_template: str = "built-in/mind_system_prompt"
    """Handlebars template for as_prompt() system prompt rendering."""

    mind_threat_analysis_template: str = "built-in/mind_threat_analysis"
    """Template for 'which need is threatened' LLM call."""

    mind_fulfill_analysis_template: str = "built-in/mind_fulfill_analysis"
    """Template for 'which need is fulfilled' LLM call."""

    mind_bias_judgment_template: str = "built-in/mind_bias_judgment"
    """Template for cognitive distortion judgment LLM call."""

    mind_impact_analysis_template: str = "built-in/mind_impact_analysis"
    """Template for emotion/intensity/personality_shift LLM call."""

    # ── Thresholds ──
    mind_personality_high: float = 70.0
    """BigFive score above this = 'high' trait."""

    mind_personality_low: float = 30.0
    """BigFive score below this = 'low' trait."""

    mind_emotion_intensity_high: float = 70.0
    """Emotion intensity above this triggers high-arousal behavior."""

    mind_emotion_intensity_mid: float = 40.0
    """Emotion intensity above this triggers mild emotional coloring."""

    mind_satisfaction_threshold: int = 3
    """Accumulated positive events needed to rise one Maslow level."""

    # ── Age brackets: (upper_bound_exclusive, shift_scale) ──
    mind_age_brackets: Tuple[Tuple[int, float], ...] = (
        (12, 3.0),
        (18, 1.5),
        (25, 0.5),
        (999, 0.2),
    )
    """Age brackets and their personality shift multipliers."""

    # ── Psychological knowledge: prose ──
    mind_need_focus: Dict[MaslowLevel, str] = field(
        default_factory=lambda: {
            MaslowLevel.PHYSIOLOGICAL: "Your entire focus is on survival: food, shelter, safety. Nothing else matters.",
            MaslowLevel.SAFETY: "You need stability and predictability. Uncertainty unsettles you.",
            MaslowLevel.BELONGING: "You crave acceptance and connection. Loneliness is your greatest fear.",
            MaslowLevel.ESTEEM: "You need respect and recognition. Failure and humiliation are unacceptable.",
            MaslowLevel.SELF_ACTUALIZATION: "You pursue meaning and purpose. Mundane concerns frustrate you.",
        }
    )
    """Maslow level -> behavioral description for prompt injection."""

    mind_bias_examples: Dict[Distortion, str] = field(
        default_factory=lambda: {
            Distortion.CATASTROPHIZING: "'He said something rude -> he must hate me -> everyone will leave'",
            Distortion.BLACK_AND_WHITE: "'Not completely loyal is betrayal, no middle ground'",
            Distortion.PERSONALIZATION: "'The team failed -> it must be my fault, I dragged everyone down'",
            Distortion.EMOTIONAL_REASONING: "'I feel incompetent -> I truly am worthless -> this is fact'",
            Distortion.SHOULD_THINKING: "'I should be able to protect everyone -> I can't -> I'm a failure'",
        }
    )
    """Cognitive distortion -> example internal monologue."""
    mind_personality_rules: Dict[PersonalityFlag, str] = field(
        default_factory=lambda: {
            PersonalityFlag.HIGH_NEUROTICISM: "You tend to anxiety, amplify threats, assume the worst",
            PersonalityFlag.LOW_AGREEABLENESS: "You are skeptical of others' motives, slow to trust",
            PersonalityFlag.HIGH_EXTRAVERSION: "You actively seek social contact, uncomfortable alone",
            PersonalityFlag.LOW_EXTRAVERSION: "You prefer solitude, find social interaction draining",
            PersonalityFlag.HIGH_CONSCIENTIOUSNESS: "You are disciplined, organized, cannot tolerate chaos",
            PersonalityFlag.HIGH_OPENNESS: "You are curious, open to new experiences and ideas",
        }
    )
    """Personality flag key -> behavioral description for prompt injection."""

    # ── Emotion -> Somatic mapping ──
    mind_emotion_somatic_map: Dict[Emotion, Tuple[SomaticState, SomaticState]] = field(
        default_factory=lambda: {
            Emotion.FEAR: (
                SomaticState(
                    heart_rate=HeartRate.RACING,
                    breathing=Breathing.RAPID,
                    muscle_tension=MuscleTension.TREMBLING,
                    facial_expression=FacialExpression.WIDE_EYES,
                    voice=VoiceQuality.TREMBLING,
                ),
                SomaticState(
                    heart_rate=HeartRate.ELEVATED,
                    breathing=Breathing.SHALLOW,
                    muscle_tension=MuscleTension.TENSE,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.STEADY,
                ),
            ),
            Emotion.ANXIETY: (
                SomaticState(
                    heart_rate=HeartRate.RACING,
                    breathing=Breathing.RAPID,
                    muscle_tension=MuscleTension.TREMBLING,
                    facial_expression=FacialExpression.WIDE_EYES,
                    voice=VoiceQuality.TREMBLING,
                ),
                SomaticState(
                    heart_rate=HeartRate.ELEVATED,
                    breathing=Breathing.SHALLOW,
                    muscle_tension=MuscleTension.TENSE,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.STEADY,
                ),
            ),
            Emotion.ANGER: (
                SomaticState(
                    heart_rate=HeartRate.RACING,
                    breathing=Breathing.RAPID,
                    muscle_tension=MuscleTension.RIGID,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.FAST,
                ),
                SomaticState(
                    heart_rate=HeartRate.RACING,
                    breathing=Breathing.RAPID,
                    muscle_tension=MuscleTension.RIGID,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.FAST,
                ),
            ),
            Emotion.RAGE: (
                SomaticState(
                    heart_rate=HeartRate.RACING,
                    breathing=Breathing.RAPID,
                    muscle_tension=MuscleTension.RIGID,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.FAST,
                ),
                SomaticState(
                    heart_rate=HeartRate.RACING,
                    breathing=Breathing.RAPID,
                    muscle_tension=MuscleTension.RIGID,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.FAST,
                ),
            ),
            Emotion.SADNESS: (
                SomaticState(
                    heart_rate=HeartRate.NORMAL,
                    breathing=Breathing.SLOW,
                    muscle_tension=MuscleTension.RELAXED,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.QUIET,
                ),
                SomaticState(
                    heart_rate=HeartRate.NORMAL,
                    breathing=Breathing.SLOW,
                    muscle_tension=MuscleTension.RELAXED,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.QUIET,
                ),
            ),
            Emotion.GRIEF: (
                SomaticState(
                    heart_rate=HeartRate.NORMAL,
                    breathing=Breathing.SLOW,
                    muscle_tension=MuscleTension.RELAXED,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.QUIET,
                ),
                SomaticState(
                    heart_rate=HeartRate.NORMAL,
                    breathing=Breathing.SLOW,
                    muscle_tension=MuscleTension.RELAXED,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.QUIET,
                ),
            ),
            Emotion.JOY: (
                SomaticState(
                    heart_rate=HeartRate.ELEVATED,
                    breathing=Breathing.NORMAL,
                    muscle_tension=MuscleTension.RELAXED,
                    facial_expression=FacialExpression.NEUTRAL,
                    voice=VoiceQuality.STEADY,
                ),
                SomaticState(
                    heart_rate=HeartRate.ELEVATED,
                    breathing=Breathing.NORMAL,
                    muscle_tension=MuscleTension.RELAXED,
                    facial_expression=FacialExpression.NEUTRAL,
                    voice=VoiceQuality.STEADY,
                ),
            ),
            Emotion.HAPPINESS: (
                SomaticState(
                    heart_rate=HeartRate.ELEVATED,
                    breathing=Breathing.NORMAL,
                    muscle_tension=MuscleTension.RELAXED,
                    facial_expression=FacialExpression.NEUTRAL,
                    voice=VoiceQuality.STEADY,
                ),
                SomaticState(
                    heart_rate=HeartRate.ELEVATED,
                    breathing=Breathing.NORMAL,
                    muscle_tension=MuscleTension.RELAXED,
                    facial_expression=FacialExpression.NEUTRAL,
                    voice=VoiceQuality.STEADY,
                ),
            ),
            Emotion.DISGUST: (
                SomaticState(
                    heart_rate=HeartRate.NORMAL,
                    breathing=Breathing.NORMAL,
                    muscle_tension=MuscleTension.TENSE,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.STEADY,
                ),
                SomaticState(
                    heart_rate=HeartRate.NORMAL,
                    breathing=Breathing.NORMAL,
                    muscle_tension=MuscleTension.TENSE,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.STEADY,
                ),
            ),
            Emotion.CONTEMPT: (
                SomaticState(
                    heart_rate=HeartRate.NORMAL,
                    breathing=Breathing.NORMAL,
                    muscle_tension=MuscleTension.TENSE,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.STEADY,
                ),
                SomaticState(
                    heart_rate=HeartRate.NORMAL,
                    breathing=Breathing.NORMAL,
                    muscle_tension=MuscleTension.TENSE,
                    facial_expression=FacialExpression.FROWN,
                    voice=VoiceQuality.STEADY,
                ),
            ),
        }
    )
    """Emotion keyword -> (high_intensity_body, low_intensity_body) mapping."""


character_config = CONFIG.load("character", CharacterConfig)
"""TOML-backed singleton with all character config values."""

__all__ = ["character_config"]
