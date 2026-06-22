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
    CharacterMind,
    CognitiveDistortion,
    Distortion,
    EmotionalState,
    EventContext,
    EventImpact,
    HeartRate,
    LinguisticStyle,
    MaslowLevel,
    MentalState,
    MuscleTension,
    NeedState,
    QualitativeSuffering,
    SituationProfile,
    SomaticState,
    SufferingSummary,
)


class UseMind(Propose, ABC):
    """Mixin providing psychological state processing capabilities.

    Inherits Propose for structured LLM output via self.propose().
    Stateless: takes MentalState as parameter, returns results.
    Caller owns MentalState as its own attribute.
    """

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
                desc for key, desc in character_config.mind_personality_rules.items() if p.personality_flag(key)
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
            has_situation=state.emotion.latest_situation is not None,
            top_situation_dimension=(
                state.emotion.latest_situation.top_dimension().value if state.emotion.latest_situation else ""
            ),
            situation_adversity=(state.emotion.latest_situation.adversity if state.emotion.latest_situation else 0.0),
            situation_negativity=(state.emotion.latest_situation.negativity if state.emotion.latest_situation else 0.0),
        )
        return TEMPLATE_MANAGER.render_template(character_config.mind_system_prompt_template, data.as_template_data())

    # -- Analysis: event -> impact --

    async def upon_event(self, event: str, state: MentalState) -> EventImpact:
        """Analyze event using targeted LLM calls with template-rendered prompts.

        Decomposes analysis into focused calls:
        - aenum_choose for MaslowLevel (threatens/fulfills need)
        - propose for DIAMONDS SituationProfile
        - ajudge for low-confidence distortion confirmation
        - CognitiveDistortion.rule_filter for distortion scoring
        - propose for QualitativeSuffering (if high intensity)

        Independent calls run in parallel via asyncio.gather.

        Pure analysis, does NOT mutate state.

        Args:
            event: The event text to analyze.
            state: Current psychological state.

        Returns:
            EventImpact with structured psychological impact analysis.
        """
        p = state.mind.personality

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

        # 3. DIAMONDS situation extraction (parallel with emotion analysis)
        diamonds_prompt = TEMPLATE_MANAGER.render_template(character_config.mind_diamonds_template, ctx_data)
        diamonds_future = self.propose(SituationProfile, diamonds_prompt)

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

        threat_result, fulfill_result, diamonds, emotion_result = await gather(
            threat_future, fulfill_future, diamonds_future, emotion_future
        )

        # 5. CBT distortion engine: rule_filter -> confidence check
        from fabricatio_character.utils import is_high_confidence, top_with_confidence

        rule_scores = state.mind.cognitive_tendencies.rule_filter(diamonds or SituationProfile())
        top_distortion, confidence = top_with_confidence(rule_scores)

        if is_high_confidence(confidence):
            triggers_distortion = top_distortion
        else:
            bias_prompt = TEMPLATE_MANAGER.render_template(
                character_config.mind_bias_judgment_template,
                {
                    **ctx_data,
                    "top_bias": top_distortion.value if top_distortion else "none",
                    "neuroticism": f"{p.neuroticism:.0f}",
                    "suffering_count": str(len(state.sufferings)),
                    "duty": f"{diamonds.duty:.2f}" if diamonds else "0",
                    "adversity": f"{diamonds.adversity:.2f}" if diamonds else "0",
                    "deception": f"{diamonds.deception:.2f}" if diamonds else "0",
                    "negativity": f"{diamonds.negativity:.2f}" if diamonds else "0",
                    "sociality": f"{diamonds.sociality:.2f}" if diamonds else "0",
                },
            )
            bias_result = await self.ajudge(bias_prompt)
            triggers_distortion = top_distortion if bias_result else None

        # 6. Suffering: create trauma for high-intensity events
        created_suffering = None
        if emotion_result and emotion_result.emotion_intensity > character_config.mind_suffering_intensity_threshold:
            suffering_prompt = TEMPLATE_MANAGER.render_template(
                character_config.mind_suffering_template,
                {
                    "event": event,
                    "emotion": emotion_result.emotion.value if emotion_result.emotion else "neutral",
                    "emotion_intensity": f"{emotion_result.emotion_intensity:.0f}",
                    "character_name": state.mind.character_name,
                },
            )
            created_suffering = await self.propose(QualitativeSuffering, suffering_prompt)

        threatens = threat_result[0] if threat_result else None
        fulfills = fulfill_result[0] if fulfill_result else None

        return EventImpact(
            threatens_need=threatens,
            fulfills_need=fulfills,
            personality_shift=emotion_result.personality_shift if emotion_result else {},
            emotion=emotion_result.emotion if emotion_result else None,
            emotion_intensity=emotion_result.emotion_intensity if emotion_result else 0.0,
            triggers_distortion=triggers_distortion,
            created_suffering=created_suffering,
            situation=diamonds,
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
        scale = character_config.age_shift_scale(age)
        for dim, delta in impact.personality_shift.items():
            if hasattr(new_state.mind.personality, dim.value):
                current = getattr(new_state.mind.personality, dim.value)
                new_val = max(0.0, min(100.0, current + delta * scale))
                setattr(new_state.mind.personality, dim.value, new_val)

        # 3. Suffering accumulation
        if impact.created_suffering is not None:
            new_state.sufferings.append(impact.created_suffering)

        # 4. Situation storage (independent of emotion — always apply if present)
        if impact.situation is not None:
            new_state.emotion = new_state.emotion.model_copy(update={"latest_situation": impact.situation})

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

    async def extract_style(self, character_name: str, dialogues: list[str]) -> LinguisticStyle:
        """Extract linguistic style from character dialogues via LLM.

        Args:
            character_name: The character's name.
            dialogues: List of dialogue strings from the character.

        Returns:
            Extracted LinguisticStyle.
        """
        prompt = TEMPLATE_MANAGER.render_template(
            character_config.mind_style_extraction_template,
            {"character_name": character_name, "dialogues": dialogues},
        )
        return await self.propose(LinguisticStyle, prompt)
