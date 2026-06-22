"""Tests for mental model data models and UseMind mixin."""

import json

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
    DistortionAnalysis,
    Emotion,
    EmotionalState,
    EventImpact,
    HeartRate,
    LinguisticStyle,
    MaslowLevel,
    MentalState,
    MuscleTension,
    NeedState,
    QualitativeSuffering,
    SituationDimension,
    SituationProfile,
    SomaticState,
    VoiceQuality,
)


class _TestMind(UseMind):
    """Concrete UseMind for testing (no LLM needed)."""

    pass


_mind = _TestMind()


def _make_state(name: str = "Test", mind: CharacterMind | None = None, **kwargs) -> MentalState:
    """Helper to create MentalState with minimal boilerplate."""
    return MentalState(mind=mind or CharacterMind(character_name=name), **kwargs)


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
# CharacterConfig helper tests
# ---------------------------------------------------------------------------


class TestAgeShiftScale:
    def test_child(self) -> None:
        from fabricatio_character.config import character_config

        assert character_config.age_shift_scale(8) == 3.0

    def test_adolescent(self) -> None:
        from fabricatio_character.config import character_config

        assert character_config.age_shift_scale(15) == 1.5

    def test_young_adult(self) -> None:
        from fabricatio_character.config import character_config

        assert character_config.age_shift_scale(20) == 0.5

    def test_adult(self) -> None:
        from fabricatio_character.config import character_config

        assert character_config.age_shift_scale(30) == 0.2


# ---------------------------------------------------------------------------
# SomaticState.from_emotion tests
# ---------------------------------------------------------------------------


class TestEmotionToSomatic:
    def test_fear_high_intensity(self) -> None:
        s = SomaticState.from_emotion(Emotion.FEAR, 80)
        assert s.heart_rate == HeartRate.RACING
        assert s.muscle_tension == MuscleTension.TREMBLING

    def test_fear_low_intensity(self) -> None:
        s = SomaticState.from_emotion(Emotion.FEAR, 40)
        assert s.heart_rate == HeartRate.ELEVATED
        assert s.muscle_tension == MuscleTension.TENSE

    def test_anger(self) -> None:
        s = SomaticState.from_emotion(Emotion.ANGER, 60)
        assert s.muscle_tension == MuscleTension.RIGID
        assert s.voice == VoiceQuality.FAST

    def test_sadness(self) -> None:
        s = SomaticState.from_emotion(Emotion.SADNESS, 50)
        assert s.voice == VoiceQuality.QUIET

    def test_neutral(self) -> None:
        s = SomaticState.from_emotion(Emotion.NEUTRAL, 0)
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
        setup_dummy_responses(
            *pad_responses(
                _codeblock('["ESTEEM"]'),
                _codeblock("true"),
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


# ---------------------------------------------------------------------------
# New tests: DIAMONDS, CBT engine, suffering, style extraction
# ---------------------------------------------------------------------------


def json_diamonds(adversity: float = 0.9, deception: float = 0.7, **overrides: float) -> str:
    """Create a JSON DIAMONDS profile string for mock responses."""
    dims: dict[str, float] = {
        "duty": 0.3,
        "intellect": 0.5,
        "adversity": adversity,
        "mating": 0.0,
        "positivity": 0.0,
        "negativity": 0.5,
        "deception": deception,
        "sociality": 0.6,
    }
    dims.update(overrides)
    return json.dumps(dims)


def json_event_impact(emotion: str = "fear", intensity: float = 50) -> str:
    """Create a JSON EventImpact string for mock responses."""
    return json.dumps({"emotion": emotion, "emotion_intensity": intensity})


def json_suffering() -> str:
    """Create a JSON QualitativeSuffering string for mock responses."""
    return json.dumps(
        {
            "what_was_lost": "sense of safety",
            "the_void": "perpetual vigilance",
            "how_it_changed_me": "cannot trust anyone",
            "anticipatory_dread": 85.0,
        }
    )


def json_linguistic_style() -> str:
    """Create a JSON LinguisticStyle string for mock responses."""
    return json.dumps(
        {
            "preferences": "formal",
            "common_pronouns": ["I"],
            "common_modals": ["should"],
            "common_adjectives": ["melancholy"],
            "style_references": ["To be..."],
        }
    )


class TestSituationProfile:
    def test_defaults(self) -> None:
        sp = SituationProfile()
        assert sp.duty == 0.0 and sp.adversity == 0.0

    def test_as_vector(self) -> None:
        assert len(SituationProfile(duty=0.5).as_vector()) == 8

    def test_top_dimension(self) -> None:
        assert SituationProfile(adversity=0.9).top_dimension() == SituationDimension.ADVERSITY

    def test_top_dimension_defaults(self) -> None:
        assert SituationProfile().top_dimension() == SituationDimension.DUTY


class TestDistortionScoring:
    def test_rule_filter_base(self) -> None:
        cd = CognitiveDistortion(catastrophizing=50, personalization=30)
        scores = cd.rule_filter(SituationProfile())
        assert scores["catastrophizing"] == 50.0
        assert scores["personalization"] == 30.0

    def test_rule_filter_boost(self) -> None:
        cd = CognitiveDistortion(catastrophizing=50)
        scores = cd.rule_filter(SituationProfile(adversity=0.8))
        assert scores["catastrophizing"] == 50.0 + 0.8 * 30.0

    def test_top_with_confidence(self) -> None:
        from fabricatio_character.utils import top_with_confidence

        top, conf = top_with_confidence({"catastrophizing": 74.0})
        assert top == Distortion.CATASTROPHIZING and conf == 74.0

    def test_top_all_zero(self) -> None:
        from fabricatio_character.utils import top_with_confidence

        top, conf = top_with_confidence({"catastrophizing": 0.0})
        assert top is None and conf == 0.0

    def test_is_high_confidence(self) -> None:
        from fabricatio_character.utils import is_high_confidence

        assert is_high_confidence(75.0) is True
        assert is_high_confidence(50.0) is False


class TestDistortionAnalysis:
    def test_defaults(self) -> None:
        da = DistortionAnalysis()
        assert da.triggered_distortion is None


class TestSufferingAccumulation:
    def test_persisted(self) -> None:
        s = QualitativeSuffering(what_was_lost="trust", the_void="suspicion", how_it_changed_me="withdrawn")
        new = _mind.after_impact(EventImpact(created_suffering=s), _make_state())
        assert len(new.sufferings) == 1

    def test_none_skipped(self) -> None:
        new = _mind.after_impact(EventImpact(created_suffering=None), _make_state())
        assert len(new.sufferings) == 0

    def test_accumulates(self) -> None:
        s1 = QualitativeSuffering(what_was_lost="a", the_void="b", how_it_changed_me="c")
        s2 = QualitativeSuffering(what_was_lost="d", the_void="e", how_it_changed_me="f")
        state = _make_state()
        state = _mind.after_impact(EventImpact(created_suffering=s1), state)
        state = _mind.after_impact(EventImpact(created_suffering=s2), state)
        assert len(state.sufferings) == 2


class _MockMindForDiamonds(UseMind):
    llm_send_to: str = DUMMY_LLM_GROUP
    llm_no_cache: bool = True


class TestUponEventDiamonds:
    def test_high_confidence_rule_result(self) -> None:
        """High adversity boosts catastrophizing -> high confidence -> rule result, no bias LLM."""
        mind = _MockMindForDiamonds()
        state = _make_state(
            mind=CharacterMind(
                character_name="Test",
                cognitive_tendencies=CognitiveDistortion(catastrophizing=60),
            )
        )
        setup_dummy_responses(
            *pad_responses(
                _codeblock('["BELONGING"]'),
                _codeblock('["ESTEEM"]'),
                _codeblock(json_diamonds()),
                _codeblock(json_event_impact(intensity=50)),
                default=_codeblock("false"),
                padding=30,
            )
        )
        import asyncio

        impact = asyncio.run(mind.upon_event("Betrayed by friend.", state))
        assert impact.triggers_distortion is not None
        assert impact.created_suffering is None

    def test_suffering_on_high_intensity(self) -> None:
        """Intensity 95 > 80 -> suffering generated. 5 calls total."""
        mind = _MockMindForDiamonds()
        state = _make_state(
            mind=CharacterMind(
                character_name="Test",
                cognitive_tendencies=CognitiveDistortion(catastrophizing=60),
            )
        )
        setup_dummy_responses(
            *pad_responses(
                _codeblock('["BELONGING"]'),
                _codeblock('["ESTEEM"]'),
                _codeblock(json_diamonds()),
                _codeblock(json_event_impact(emotion="grief", intensity=95)),
                _codeblock(json_suffering()),
                default=_codeblock("false"),
                padding=30,
            )
        )
        import asyncio

        impact = asyncio.run(mind.upon_event("Family killed.", state))
        assert impact.created_suffering is not None

    def test_low_confidence_uses_llm(self) -> None:
        """Low base tendency + low adversity -> low confidence -> ajudge called. 5 calls."""
        mind = _MockMindForDiamonds()
        state = _make_state(
            mind=CharacterMind(
                character_name="Test",
                cognitive_tendencies=CognitiveDistortion(catastrophizing=10),
            )
        )
        setup_dummy_responses(
            *pad_responses(
                _codeblock('["BELONGING"]'),
                _codeblock('["ESTEEM"]'),
                _codeblock(json_diamonds(adversity=0.1)),
                _codeblock(json_event_impact(emotion="sadness", intensity=30)),
                _codeblock("true"),
                default=_codeblock("false"),
                padding=30,
            )
        )
        import asyncio

        impact = asyncio.run(mind.upon_event("Minor setback.", state))
        assert impact.emotion == Emotion.SADNESS


class TestExtractStyle:
    def test_extract(self) -> None:
        mind = _MockMindForDiamonds()
        setup_dummy_responses(
            *pad_responses(
                _codeblock(json_linguistic_style()),
                default=_codeblock("{}"),
                padding=20,
            )
        )
        import asyncio

        style = asyncio.run(mind.extract_style("Hamlet", ["To be..."]))
        assert isinstance(style, LinguisticStyle)
        assert style.common_adjectives == ["melancholy"]
