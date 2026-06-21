"""UseMind mixin: processes events and updates character psychological state.

Implements the three-layer architecture:
1. Analysis (LLM) - upon_event(): event -> EventImpact
2. Update (rules) - after_impact(): EventImpact -> new MentalState
3. Alignment (template) - as_prompt(): MentalState -> system prompt string

Usage::

    class MyCharacter(UseMind):
        mental_state: MentalState

        async def handle_event(self, event: str) -> str:
            impact = await self.upon_event(event, self.mental_state)
            self.mental_state = self.after_impact(impact, self.mental_state)
            return self.as_prompt(self.mental_state)
"""

from abc import ABC
from asyncio import gather

from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.rust import TEMPLATE_MANAGER

from fabricatio_character.config import character_config
from fabricatio_character.models.mental import (
    AsPromptData,
    BigFiveProfile,
    CharacterMind,
    CognitiveDistortion,
    Distortion,
    Emotion,
    EmotionalState,
    EventContext,
    EventImpact,
    HeartRate,
    MaslowLevel,
    MentalState,
    MuscleTension,
    NeedState,
    PersonalityFlag,
    SomaticState,
    SufferingSummary,
)


class UseMind(Propose, ABC):
    """Mixin providing psychological state processing capabilities.

    Inherits Propose for structured LLM output via self.propose().
    Stateless: takes MentalState as parameter, returns results.
    Caller owns MentalState as its own attribute.
    """

    # -- Internal helpers --

    def _age_shift_scale(self, age: int) -> float:
        """Return personality shift scale based on age from config brackets."""
        for upper, scale in character_config.mind_age_brackets:
            if age < upper:
                return scale
        return 0.2

    def _resolve_emotion_somatic(self, emotion: Emotion, intensity: float) -> SomaticState:
        """Deterministic mapping from emotion to body sensations via config."""
        entry = character_config.mind_emotion_somatic_map.get(emotion)
        if entry is None:
            return SomaticState()
        high_state, low_state = entry
        return high_state if intensity > character_config.mind_emotion_intensity_high else low_state

    def _personality_flag(self, flag: PersonalityFlag, p: BigFiveProfile) -> bool:
        """Check a personality condition flag against the profile."""
        high = character_config.mind_personality_high
        low = character_config.mind_personality_low
        flag_map = {
            PersonalityFlag.HIGH_NEUROTICISM: p.neuroticism > high,
            PersonalityFlag.LOW_AGREEABLENESS: p.agreeableness < low,
            PersonalityFlag.HIGH_EXTRAVERSION: p.extraversion > high,
            PersonalityFlag.LOW_EXTRAVERSION: p.extraversion < low,
            PersonalityFlag.HIGH_CONSCIENTIOUSNESS: p.conscientiousness > high,
            PersonalityFlag.HIGH_OPENNESS: p.openness > high,
        }
        return flag_map.get(flag, False)

    # -- Seeding: CharacterCard -> MentalState --

    async def seed_from(self, name: str, want: str, flaw: str) -> MentalState:
        """Seed MentalState from character description using LLM.

        Uses aenum_choose to determine initial MaslowLevel from want text,
        and ajudge to determine which cognitive distortions apply from flaw text.

        Args:
            name: Character name.
            want: Character's core motivation/goal.
            flaw: Character's critical weakness/vulnerability.

        Returns:
            Seeded MentalState.
        """
        # Determine initial need level via LLM
        need_future = self.aenum_choose(
            f"Given this character motivation: '{want}'\nWhich need level best describes their primary drive?",
            MaslowLevel,
            k=1,
        )

        # Determine which distortions apply via LLM judgments
        distortion_futures = {
            dist: self.ajudge(f"Does this character flaw suggest {dist.value}?\nFlaw: '{flaw}'") for dist in Distortion
        }

        need_result = await need_future
        distortion_results = {dist: await future for dist, future in distortion_futures.items()}

        initial_need = need_result[0] if need_result else MaslowLevel.BELONGING

        cognitive = CognitiveDistortion()
        for dist, triggered in distortion_results.items():
            if triggered:
                setattr(cognitive, dist.value, 70.0)

        return MentalState(
            mind=CharacterMind(
                character_name=name,
                cognitive_tendencies=cognitive,
            ),
            needs=NeedState(current_level=initial_need),
        )

    # -- Alignment: state -> prompt --

    def as_prompt(self, state: MentalState) -> str:
        """Translate MentalState into LLM system prompt via template.

        Uses AsPromptData model for typed template data.

        Args:
            state: Current psychological state.

        Returns:
            Rendered system prompt string.
        """
        p = state.mind.personality
        s = state.emotion.somatic
        ls = state.mind.linguistic_style

        active_distortion = state.emotion.active_distortion

        data = AsPromptData(
            personality_rules=[
                desc for key, desc in character_config.mind_personality_rules.items() if self._personality_flag(key, p)
            ],
            need_description=character_config.mind_need_focus.get(state.needs.current_level, ""),
            emotion=state.emotion.emotion.value,
            emotion_intensity=f"{state.emotion.intensity:.0f}",
            emotion_high=state.emotion.intensity > character_config.mind_emotion_intensity_high,
            emotion_mid=state.emotion.intensity > character_config.mind_emotion_intensity_mid,
            cognitive_bias=active_distortion.value if active_distortion else None,
            bias_example=character_config.mind_bias_examples.get(active_distortion, "") if active_distortion else "",
            has_somatic=s.heart_rate != HeartRate.NORMAL or s.muscle_tension != MuscleTension.RELAXED,
            somatic_heart_rate=s.heart_rate.value,
            somatic_breathing=s.breathing.value,
            somatic_muscle_tension=s.muscle_tension.value,
            somatic_facial_expression=s.facial_expression.value,
            somatic_voice=s.voice.value,
            has_sufferings=bool(state.sufferings),
            sufferings=[
                SufferingSummary(
                    what_was_lost=sv.what_was_lost,
                    the_void=sv.the_void,
                    how_it_changed_me=sv.how_it_changed_me,
                )
                for sv in state.sufferings
            ],
            has_linguistic=bool(ls.preferences),
            linguistic_preferences=ls.preferences,
            linguistic_pronouns=ls.common_pronouns or None,
            linguistic_modals=ls.common_modals or None,
        )
        return TEMPLATE_MANAGER.render_template(character_config.mind_system_prompt_template, data.as_template_data())

    # -- Analysis: event -> impact --

    async def upon_event(self, event: str, state: MentalState) -> EventImpact:
        """Analyze event using targeted LLM calls with template-rendered prompts.

        Decomposes analysis into focused calls:
        - aenum_choose for MaslowLevel (threatens/fulfills need)
        - ajudge for cognitive distortion activation
        - propose for structured EventImpact (emotion, intensity, personality_shift)

        Independent calls run in parallel via asyncio.gather.

        Pure analysis, does NOT mutate state.

        Args:
            event: The event text to analyze.
            state: Current psychological state.

        Returns:
            EventImpact with structured psychological impact analysis.
        """
        p = state.mind.personality
        top_bias = state.mind.cognitive_tendencies.top(1)[0]

        ctx = EventContext(
            event=event,
            emotion=state.emotion.emotion,
            emotion_intensity=state.emotion.intensity,
            current_need=state.needs.current_level,
        )
        ctx_data = ctx.as_template_data()

        # 1. Which need does this event threaten?
        threat_prompt = TEMPLATE_MANAGER.render_template(character_config.mind_threat_analysis_template, ctx_data)
        threat_future = self.aenum_choose(threat_prompt, MaslowLevel, k=1)

        # 2. Which need does this event fulfill?
        fulfill_prompt = TEMPLATE_MANAGER.render_template(character_config.mind_fulfill_analysis_template, ctx_data)
        fulfill_future = self.aenum_choose(fulfill_prompt, MaslowLevel, k=1)

        # 3. Does this event trigger the character's top cognitive distortion?
        bias_prompt = TEMPLATE_MANAGER.render_template(
            character_config.mind_bias_judgment_template,
            {
                **ctx_data,
                "top_bias": top_bias.value,
                "neuroticism": f"{p.neuroticism:.0f}",
                "suffering_count": str(len(state.sufferings)),
            },
        )
        bias_future = self.ajudge(bias_prompt)

        # 4. What emotion + intensity + personality shift?
        impact_prompt = TEMPLATE_MANAGER.render_template(
            character_config.mind_impact_analysis_template,
            {
                **ctx_data,
                "o": f"{p.openness:.0f}",
                "c": f"{p.conscientiousness:.0f}",
                "e": f"{p.extraversion:.0f}",
                "a": f"{p.agreeableness:.0f}",
                "n": f"{p.neuroticism:.0f}",
                "suffering_count": str(len(state.sufferings)),
            },
        )
        emotion_future = self.propose(EventImpact, impact_prompt)

        threat_result, fulfill_result, bias_result, emotion_result = await gather(
            threat_future, fulfill_future, bias_future, emotion_future
        )

        threatens = threat_result[0] if threat_result else None
        fulfills = fulfill_result[0] if fulfill_result else None
        triggers_distortion = top_bias if bias_result else None

        return EventImpact(
            threatens_need=threatens,
            fulfills_need=fulfills,
            personality_shift=emotion_result.personality_shift if emotion_result else {},
            emotion=emotion_result.emotion if emotion_result else None,
            emotion_intensity=emotion_result.emotion_intensity if emotion_result else 0.0,
            triggers_distortion=triggers_distortion,
        )

    # -- Update: impact -> new state --

    def after_impact(self, impact: EventImpact, state: MentalState, age: int = 25) -> MentalState:
        """Apply deterministic rules to update MentalState from EventImpact.

        Returns a NEW MentalState (immutable update).

        Args:
            impact: Structured impact from event analysis.
            state: Current psychological state.
            age: Character age (affects personality drift scale).

        Returns:
            New MentalState with impact applied.
        """
        new_state = state.model_copy(deep=True)

        # 1. Need transitions
        if impact.threatens_need is not None:
            new_state = new_state.drop_level(impact.threatens_need)
        if impact.fulfills_need is not None:
            new_state = new_state.accumulate_satisfaction(impact.fulfills_need)

        # 2. Personality drift (age-scaled)
        scale = self._age_shift_scale(age)
        for dim, delta in impact.personality_shift.items():
            if hasattr(new_state.mind.personality, dim.value):
                current = getattr(new_state.mind.personality, dim.value)
                new_val = max(0.0, min(100.0, current + delta * scale))
                setattr(new_state.mind.personality, dim.value, new_val)

        # 3. Emotional state (replace, not mutate)
        if impact.emotion is not None:
            new_state.emotion = EmotionalState(
                emotion=impact.emotion,
                intensity=impact.emotion_intensity,
                somatic=self._resolve_emotion_somatic(impact.emotion, impact.emotion_intensity),
                active_distortion=impact.triggers_distortion,
            )

        return new_state
