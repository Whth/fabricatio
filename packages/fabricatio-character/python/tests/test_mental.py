"""Tests for mental model data models and UseMind mixin."""

import pytest

from fabricatio_mock import DUMMY_LLM_GROUP
from fabricatio_mock.models.mock_router import pad_responses
from fabricatio_mock.utils import setup_dummy_responses
from fabricatio_character.capabilities.mental import UseMind
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.models.mental import (
    BigFiveProfile,
    CharacterMind,
    CognitiveDistortion,
    Distortion,
    Emotion,
    EmotionalState,
    EventImpact,
    HeartRate,
    MaslowLevel,
    MentalState,
    MuscleTension,
    NeedState,
    QualitativeSuffering,
    SomaticState,
    VoiceQuality,
)


class _TestMind(UseMind):
    """Concrete UseMind for testing (no LLM needed)."""

    pass


_mind = _TestMind()


def _make_state(name: str = "Test", **kwargs) -> MentalState:
    """Helper to create MentalState with minimal boilerplate."""
    return MentalState(mind=CharacterMind(character_name=name), **kwargs)


# ---------------------------------------------------------------------------
# BigFiveProfile tests
# ---------------------------------------------------------------------------


class TestBigFiveProfile:
    def test_default_values(self) -> None:
        p = BigFiveProfile()
        assert p.openness == 50.0
        assert p.neuroticism == 50.0

    def test_as_vector(self) -> None:
        vec = BigFiveProfile(openness=80, neuroticism=20).as_vector()
        assert len(vec) == 5
        assert vec[0] == 80.0
        assert vec[4] == 20.0

    def test_distance_to_self(self) -> None:
        p = BigFiveProfile()
        assert p.distance_to(p) == 0.0

    def test_distance_to_different(self) -> None:
        a = BigFiveProfile(openness=100, neuroticism=0)
        b = BigFiveProfile(openness=0, neuroticism=100)
        assert a.distance_to(b) > 0

    def test_clamp_bounds(self) -> None:
        with pytest.raises(Exception):
            BigFiveProfile(openness=101)
        with pytest.raises(Exception):
            BigFiveProfile(openness=-1)


# ---------------------------------------------------------------------------
# MaslowLevel tests
# ---------------------------------------------------------------------------


class TestMaslowLevel:
    def test_ordering(self) -> None:
        assert (
            MaslowLevel.PHYSIOLOGICAL
            < MaslowLevel.SAFETY
            < MaslowLevel.BELONGING
            < MaslowLevel.ESTEEM
            < MaslowLevel.SELF_ACTUALIZATION
        )

    def test_values(self) -> None:
        assert MaslowLevel.PHYSIOLOGICAL == 1
        assert MaslowLevel.SELF_ACTUALIZATION == 5


# ---------------------------------------------------------------------------
# CognitiveDistortion tests
# ---------------------------------------------------------------------------


class TestCognitiveDistortion:
    def test_top(self) -> None:
        cd = CognitiveDistortion(catastrophizing=80, personalization=60)
        result = cd.top(1)
        assert result == [Distortion.CATASTROPHIZING]

    def test_top_multiple(self) -> None:
        cd = CognitiveDistortion(catastrophizing=80, personalization=60, should_thinking=70)
        result = cd.top(2)
        assert result[0] == Distortion.CATASTROPHIZING
        assert result[1] == Distortion.SHOULD_THINKING


# ---------------------------------------------------------------------------
# SomaticState / EmotionalState / EventImpact tests
# ---------------------------------------------------------------------------


class TestSomaticState:
    def test_defaults(self) -> None:
        s = SomaticState()
        assert s.heart_rate == HeartRate.NORMAL
        assert s.muscle_tension == MuscleTension.RELAXED


class TestEventImpact:
    def test_defaults(self) -> None:
        i = EventImpact()
        assert i.threatens_need is None
        assert i.emotion is None
        assert i.emotion_intensity == 0


# ---------------------------------------------------------------------------
# MentalState tests
# ---------------------------------------------------------------------------


class TestMentalState:
    def test_defaults(self) -> None:
        state = _make_state()
        assert state.mind.character_name == "Test"
        assert state.needs.current_level == MaslowLevel.PHYSIOLOGICAL
        assert state.emotion.emotion == Emotion.NEUTRAL
        assert state.emotion.somatic.heart_rate == HeartRate.NORMAL

    def test_from_card_sets_name(self) -> None:
        card = CharacterCard(name="Hero", role="protagonist", look="tall", act="brave", want="love", flaw="anxious")
        state = MentalState.from_card(card)
        assert state.mind.character_name == "Hero"
        assert state.needs.current_level == MaslowLevel.PHYSIOLOGICAL  # default
        assert state.mind.cognitive_tendencies.catastrophizing == 20.0  # default


# ---------------------------------------------------------------------------
# UseMind helper tests
# ---------------------------------------------------------------------------


class TestAgeShiftScale:
    def test_child(self) -> None:
        assert _mind._age_shift_scale(8) == 3.0

    def test_adolescent(self) -> None:
        assert _mind._age_shift_scale(15) == 1.5

    def test_young_adult(self) -> None:
        assert _mind._age_shift_scale(20) == 0.5

    def test_adult(self) -> None:
        assert _mind._age_shift_scale(30) == 0.2


class TestEmotionToSomatic:
    def test_fear_high_intensity(self) -> None:
        s = _mind._resolve_emotion_somatic(Emotion.FEAR, 80)
        assert s.heart_rate == HeartRate.RACING
        assert s.muscle_tension == MuscleTension.TREMBLING

    def test_fear_low_intensity(self) -> None:
        s = _mind._resolve_emotion_somatic(Emotion.FEAR, 40)
        assert s.heart_rate == HeartRate.ELEVATED
        assert s.muscle_tension == MuscleTension.TENSE

    def test_anger(self) -> None:
        s = _mind._resolve_emotion_somatic(Emotion.ANGER, 60)
        assert s.muscle_tension == MuscleTension.RIGID
        assert s.voice == VoiceQuality.FAST

    def test_sadness(self) -> None:
        s = _mind._resolve_emotion_somatic(Emotion.SADNESS, 50)
        assert s.voice == VoiceQuality.QUIET

    def test_neutral(self) -> None:
        s = _mind._resolve_emotion_somatic(Emotion.NEUTRAL, 0)
        assert s.heart_rate == HeartRate.NORMAL


# ---------------------------------------------------------------------------
# UseMind.after_impact tests
# ---------------------------------------------------------------------------


class TestAfterImpact:
    def test_threat(self) -> None:
        state = _make_state(
            needs=NeedState(
                current_level=MaslowLevel.BELONGING,
                satisfied=[MaslowLevel.PHYSIOLOGICAL, MaslowLevel.SAFETY],
            )
        )
        new_state = _mind.after_impact(EventImpact(threatens_need=MaslowLevel.SAFETY), state)
        assert new_state.needs.current_level < MaslowLevel.SAFETY
        assert state.needs.current_level == MaslowLevel.BELONGING  # immutable

    def test_fulfill(self) -> None:
        state = _make_state(needs=NeedState(current_level=MaslowLevel.PHYSIOLOGICAL))
        for _ in range(3):
            state = _mind.after_impact(EventImpact(fulfills_need=MaslowLevel.PHYSIOLOGICAL), state)
        assert MaslowLevel.PHYSIOLOGICAL in state.needs.satisfied
        assert state.needs.current_level > MaslowLevel.PHYSIOLOGICAL

    def test_emotion(self) -> None:
        new_state = _mind.after_impact(EventImpact(emotion=Emotion.FEAR, emotion_intensity=80), _make_state())
        assert new_state.emotion.emotion == Emotion.FEAR
        assert new_state.emotion.intensity == 80
        assert new_state.emotion.somatic.heart_rate == HeartRate.RACING

    def test_active_distortion(self) -> None:
        new_state = _mind.after_impact(
            EventImpact(emotion=Emotion.FEAR, emotion_intensity=80, triggers_distortion=Distortion.CATASTROPHIZING),
            _make_state(),
        )
        assert new_state.emotion.active_distortion == Distortion.CATASTROPHIZING

    def test_age_aware_drift(self) -> None:
        from fabricatio_character.models.mental import BigFiveDimension

        state = _make_state()
        impact = EventImpact(personality_shift={BigFiveDimension.NEUROTICISM: 10.0})
        child = _mind.after_impact(impact, state, age=8)
        adult = _mind.after_impact(impact, state, age=30)
        assert child.mind.personality.neuroticism > adult.mind.personality.neuroticism

    def test_model_copy_deep(self) -> None:
        state = _make_state()
        copied = state.model_copy(deep=True)
        copied.mind.personality.openness = 99
        assert state.mind.personality.openness == 50.0


# ---------------------------------------------------------------------------
# UseMind.as_prompt tests
# ---------------------------------------------------------------------------


class TestAsPrompt:
    def test_basic(self) -> None:
        prompt = _mind.as_prompt(_make_state())
        assert "Current Need" in prompt or "Personality" in prompt

    def test_with_bias(self) -> None:
        state = _make_state(emotion=EmotionalState(active_distortion=Distortion.CATASTROPHIZING))
        assert "catastrophizing" in _mind.as_prompt(state)

    def test_with_suffering(self) -> None:
        state = _make_state(
            sufferings=[
                QualitativeSuffering(
                    what_was_lost="trust", the_void="always suspicious", how_it_changed_me="became withdrawn"
                ),
            ]
        )


# ---------------------------------------------------------------------------
# UseMind.seed_from tests (with mock LLM)
# ---------------------------------------------------------------------------


def _codeblock(content: str) -> str:
    """Wrap content in markdown code block for JSON parser."""
    return f"```json\n{content}\n```"


class _MockMind(UseMind):
    """UseMind with mock LLM for testing seed_from()."""

    llm_send_to: str = DUMMY_LLM_GROUP
    llm_no_cache: bool = True


class TestSeedFrom:
    def test_seed_from_need_and_distortion(self) -> None:
        """seed_from() uses aenum_choose for need and ajudge for distortions."""
        mind = _MockMind()
        # FIFO order: first added = first consumed (setup_dummy_responses reverses for LIFO).
        # aenum_choose: needs code-block-wrapped JSON array
        # ajudge x5: needs code-block-wrapped booleans
        # Pad with "false" for retry safety (max_validations=3)
        setup_dummy_responses(
            *pad_responses(
                _codeblock('["ESTEEM"]'),  # aenum_choose result
                _codeblock("true"),  # ajudge: catastrophizing = true
                default=_codeblock("false"),
                padding=20,
            )
        )
        import asyncio

        state = asyncio.run(
            mind.seed_from(
                name="Hamlet",
                want="To avenge his father's murder",
                flaw="Tendency toward catastrophizing",
            )
        )
        assert state.mind.character_name == "Hamlet"
        assert state.needs.current_level == MaslowLevel.ESTEEM
        assert state.mind.cognitive_tendencies.catastrophizing == 70.0
