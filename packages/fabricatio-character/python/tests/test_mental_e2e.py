"""End-to-end test using literary character scenarios.

Tests the full pipeline: CharacterCard -> MentalState -> event processing -> prompt generation.
Uses Hamlet and Lin Daiyu as test characters.
"""

from fabricatio_character.capabilities.mental import UseMind
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.models.mental import (
    BigFiveDimension,
    CharacterMind,
    CognitiveDistortion,
    Distortion,
    Emotion,
    EmotionalState,
    EventImpact,
    MaslowLevel,
    MentalState,
    NeedState,
    QualitativeSuffering,
    VoiceQuality,
)


class _TestMind(UseMind):
    pass


_mind = _TestMind()


def _make_state(name: str = "Test", **kwargs) -> MentalState:
    """Helper to create MentalState with minimal boilerplate."""
    return MentalState(mind=CharacterMind(character_name=name), **kwargs)


def _make_hamlet() -> CharacterCard:
    return CharacterCard(
        name="Hamlet",
        role="Prince of Denmark, tragic protagonist",
        look="Young prince, melancholic bearing, dark clothing",
        act="Indecisive, philosophical, prone to soliloquies, oscillates between action and contemplation",
        want="To avenge his father's murder while reconciling his moral conscience with the duty of revenge",
        flaw="Paralyzing indecision rooted in over-intellectualization; tendency toward catastrophizing and existential despair",
    )


def _make_daiyu() -> CharacterCard:
    return CharacterCard(
        name="Lin Daiyu",
        role="Tragic heroine of Dream of the Red Chamber",
        look="Fragile, ethereal beauty, often coughing blood",
        act="Poetic, sharp-tongued, deeply sensitive, prone to weeping",
        want="To be loved unconditionally by Jia Baoyu and to find belonging in the Jia household",
        flaw="Extreme sensitivity and jealousy; interprets ambiguity as rejection; emotional reasoning dominates",
    )


def _hamlet_state() -> MentalState:
    """Hamlet with ESTEEM need and catastrophizing tendency (as if seeded by LLM)."""
    return MentalState(
        mind=CharacterMind(
            character_name="Hamlet",
            cognitive_tendencies=CognitiveDistortion(catastrophizing=70.0),
        ),
        needs=NeedState(current_level=MaslowLevel.ESTEEM),
    )


def _daiyu_state() -> MentalState:
    """Daiyu with BELONGING need and emotional_reasoning tendency (as if seeded by LLM)."""
    return MentalState(
        mind=CharacterMind(
            character_name="Lin Daiyu",
            cognitive_tendencies=CognitiveDistortion(emotional_reasoning=70.0),
        ),
        needs=NeedState(current_level=MaslowLevel.BELONGING),
    )


class TestHamletScenario:
    def test_from_card_sets_name(self) -> None:
        state = MentalState.from_card(_make_hamlet())
        assert state.mind.character_name == "Hamlet"
        assert state.needs.current_level == MaslowLevel.PHYSIOLOGICAL  # default

    def test_father_murder_event(self) -> None:
        state = _hamlet_state()
        impact = EventImpact(
            threatens_need=MaslowLevel.ESTEEM,
            emotion=Emotion.GRIEF,
            emotion_intensity=90,
            triggers_distortion=Distortion.CATASTROPHIZING,
            personality_shift={BigFiveDimension.NEUROTICISM: 5.0},
        )
        state = _mind.after_impact(impact, state, age=20)

        assert state.emotion.emotion == Emotion.GRIEF
        assert state.emotion.intensity == 90
        assert state.emotion.active_distortion == Distortion.CATASTROPHIZING
        assert state.emotion.somatic.voice == VoiceQuality.QUIET
        assert state.mind.personality.neuroticism > 50.0

    def test_mother_remarriage_event(self) -> None:
        state = _hamlet_state()

        state = _mind.after_impact(
            EventImpact(threatens_need=MaslowLevel.ESTEEM, emotion=Emotion.GRIEF, emotion_intensity=90),
            state,
            age=20,
        )

        state = _mind.after_impact(
            EventImpact(
                threatens_need=MaslowLevel.BELONGING,
                emotion=Emotion.DISGUST,
                emotion_intensity=70,
                triggers_distortion=Distortion.PERSONALIZATION,
            ),
            state,
            age=20,
        )

        assert state.emotion.emotion == Emotion.DISGUST
        assert state.emotion.active_distortion == Distortion.PERSONALIZATION
        assert MaslowLevel.BELONGING not in state.needs.satisfied

    def test_build_prompt_after_trauma(self) -> None:
        state = _hamlet_state()
        state = _mind.after_impact(
            EventImpact(
                threatens_need=MaslowLevel.ESTEEM,
                emotion=Emotion.GRIEF,
                emotion_intensity=90,
                triggers_distortion=Distortion.CATASTROPHIZING,
            ),
            state,
            age=20,
        )
        state.sufferings.append(
            QualitativeSuffering(
                what_was_lost="father",
                the_void="no guiding figure, orphaned in purpose",
                how_it_changed_me="became obsessed with mortality and revenge",
            )
        )

        prompt = _mind.as_prompt(state)
        assert "grief" in prompt.lower() or "90" in prompt
        assert "catastrophizing" in prompt
        assert "father" in prompt


class TestDaiyuScenario:
    def test_from_card_sets_name(self) -> None:
        state = MentalState.from_card(_make_daiyu())
        assert state.mind.character_name == "Lin Daiyu"

    def test_baoyu_gives_old_handkerchief(self) -> None:
        state = _daiyu_state()
        for _ in range(3):
            state = _mind.after_impact(
                EventImpact(fulfills_need=MaslowLevel.BELONGING, emotion=Emotion.JOY, emotion_intensity=60),
                state,
                age=15,
            )
        assert MaslowLevel.BELONGING in state.needs.satisfied
        assert state.needs.current_level > MaslowLevel.BELONGING

    def test_baoyu_marries_baochai(self) -> None:
        state = _daiyu_state()
        for _ in range(3):
            state = _mind.after_impact(
                EventImpact(fulfills_need=MaslowLevel.BELONGING, emotion=Emotion.JOY, emotion_intensity=60),
                state,
                age=17,
            )

        state = _mind.after_impact(
            EventImpact(
                threatens_need=MaslowLevel.BELONGING,
                emotion=Emotion.SADNESS,
                emotion_intensity=100,
                triggers_distortion=Distortion.EMOTIONAL_REASONING,
                personality_shift={BigFiveDimension.NEUROTICISM: 10.0},
            ),
            state,
            age=17,
        )

        assert state.emotion.emotion == Emotion.SADNESS
        assert state.emotion.intensity == 100
        assert state.emotion.active_distortion == Distortion.EMOTIONAL_REASONING
        assert state.emotion.somatic.voice == VoiceQuality.QUIET


class TestMaslowDynamics:
    def test_threat_drops_level(self) -> None:
        state = _make_state(
            needs=NeedState(
                current_level=MaslowLevel.ESTEEM,
                satisfied=[MaslowLevel.PHYSIOLOGICAL, MaslowLevel.SAFETY, MaslowLevel.BELONGING],
            )
        )
        state = _mind.after_impact(EventImpact(threatens_need=MaslowLevel.SAFETY), state)

        assert MaslowLevel.SAFETY not in state.needs.satisfied
        assert MaslowLevel.BELONGING not in state.needs.satisfied
        assert state.needs.current_level < MaslowLevel.SAFETY

    def test_satisfaction_accumulates_then_rises(self) -> None:
        state = _make_state(needs=NeedState(current_level=MaslowLevel.PHYSIOLOGICAL))

        state = _mind.after_impact(EventImpact(fulfills_need=MaslowLevel.PHYSIOLOGICAL), state)
        state = _mind.after_impact(EventImpact(fulfills_need=MaslowLevel.PHYSIOLOGICAL), state)
        assert state.needs.current_level == MaslowLevel.PHYSIOLOGICAL

        state = _mind.after_impact(EventImpact(fulfills_need=MaslowLevel.PHYSIOLOGICAL), state)
        assert state.needs.current_level > MaslowLevel.PHYSIOLOGICAL
        assert MaslowLevel.PHYSIOLOGICAL in state.needs.satisfied
