"""UseMind mixin: psychological analysis capabilities over a model-owned MentalState.

The state object owns everything deterministic — rule application
(``MentalState.apply``), prompt rendering (``MentalState.as_prompt``, AsPrompt
protocol), and persistence (``PersistentAble``). This mixin owns only the
LLM-facing half:

1. ``seed_from(card)``: CharacterCard -> LLM-judged initial MentalState
2. ``observe(event, state)``: event -> EventImpact (pure analysis, no mutation)
3. ``react(event, state)``: observe + apply — the one-call event handler

Usage::

    class MyCharacter(UseMind, CharacterCompose):
        pass

    agent = MyCharacter()
    card = await agent.compose_characters("Hamlet, prince of Denmark")
    mind = await agent.seed_from(card, age=30)
    mind = await agent.react("The ghost accuses your uncle.", mind)
    prompt = mind.as_prompt()
"""

from abc import ABC
from asyncio import gather

from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.rust import TASK, TEMPLATE_MANAGER

from fabricatio_character.config import character_config
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.models.mental import (
    CharacterMind,
    CognitiveDistortion,
    Distortion,
    EventContext,
    EventImpact,
    LinguisticStyle,
    MaslowLevel,
    MentalState,
    NeedState,
    QualitativeSuffering,
    SituationProfile,
)


class UseMind(Propose, ABC):
    """Mixin providing psychological analysis capabilities.

    Inherits Propose for structured LLM output via self.propose().
    Stateless: takes MentalState as parameter, returns results. The caller
    keeps ownership of the state; every update path returns a new instance.
    """

    # -- Seeding: CharacterCard -> MentalState --

    async def seed_from(self, card: CharacterCard, age: int = 25, send_to: str | None = TASK) -> MentalState:
        """Seed MentalState from a CharacterCard using LLM judgment.

        Uses aenum_choose to determine the initial MaslowLevel from the
        card's ``want`` text, and ajudge to determine which cognitive
        distortions apply from the card's ``flaw`` text.

        Args:
            card: Character card providing name, want, and flaw.
            age: Character age, stored on the mind and reused by ``apply``.
            send_to: Routing group for LLM calls (TASK/SMOL/TINY/SLOW/PLAN).

        Returns:
            Seeded MentalState.
        """
        # Determine initial need level via LLM
        need_future = self.aenum_choose(
            f"Given this character motivation: '{card.want}'\nWhich need level best describes their primary drive?",
            MaslowLevel,
            k=1,
            send_to=send_to,
        )

        # Determine which distortions apply via LLM judgments
        distortion_futures = {
            dist: self.ajudge(
                f"Does this character flaw suggest {dist.value}?\nFlaw: '{card.flaw}'",
                send_to=send_to,
            )
            for dist in Distortion
        }

        need_result = await need_future
        distortion_results = {dist: await future for dist, future in distortion_futures.items()}

        initial_need = need_result[0] if need_result else MaslowLevel.BELONGING

        cognitive = CognitiveDistortion().raised({dist: 70.0 for dist, hit in distortion_results.items() if hit})

        return MentalState(
            mind=CharacterMind(character_name=card.name, age=age, cognitive_tendencies=cognitive),
            needs=NeedState(current_level=initial_need),
        )

    # -- Analysis: event -> impact --

    async def observe(self, event: str, state: MentalState, send_to: str | None = TASK) -> EventImpact:
        """Analyze event using targeted LLM calls with template-rendered prompts.

        Decomposes analysis into focused calls:
        - aenum_choose for MaslowLevel (threatens/fulfills need)
        - propose for DIAMONDS SituationProfile
        - ajudge for low-confidence distortion confirmation
        - CognitiveDistortion.rule_filter for distortion scoring
        - propose for QualitativeSuffering (if high intensity)

        Independent calls run in parallel via asyncio.gather.

        Pure analysis, does NOT mutate state. To evolve the state, pass the
        returned impact to ``state.apply(impact)`` or use :meth:`react`.

        Args:
            event: The event text to analyze.
            state: Current psychological state.
            send_to: Routing group for LLM calls (TASK/SMOL/TINY/SLOW/PLAN).

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

        # 1. Judge if event threatens/fulfills any need (parallel)
        threat_judge_prompt = TEMPLATE_MANAGER.render_template(character_config.mind_threat_analysis_template, ctx_data)
        threat_judge_future = self.ajudge(threat_judge_prompt, send_to=send_to)

        fulfill_judge_prompt = TEMPLATE_MANAGER.render_template(
            character_config.mind_fulfill_analysis_template,
            ctx_data,
        )
        fulfill_judge_future = self.ajudge(fulfill_judge_prompt, send_to=send_to)

        # 2. DIAMONDS situation extraction (parallel)
        diamonds_prompt = TEMPLATE_MANAGER.render_template(character_config.mind_diamonds_template, ctx_data)
        diamonds_future = self.propose(SituationProfile, diamonds_prompt, send_to=send_to)

        # 3. What emotion + intensity + personality shift? (parallel)
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
        emotion_future = self.propose(EventImpact, impact_prompt, send_to=send_to)

        threat_judge, fulfill_judge, diamonds, emotion_result = await gather(
            threat_judge_future,
            fulfill_judge_future,
            diamonds_future,
            emotion_future,
        )

        # 4. Select specific need level only if judge affirmed

        threat_result = None
        if threat_judge:
            select_prompt = f"Which specific Maslow need level does this event THREATEN?\nEvent: {event}"
            threat_result = await self.aenum_choose(select_prompt, MaslowLevel, k=1, send_to=send_to)

        fulfill_result = None
        if fulfill_judge:
            select_prompt = f"Which specific Maslow need level does this event FULFILL?\nEvent: {event}"
            fulfill_result = await self.aenum_choose(select_prompt, MaslowLevel, k=1, send_to=send_to)

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
            bias_result = await self.ajudge(bias_prompt, send_to=send_to)
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
            created_suffering = await self.propose(QualitativeSuffering, suffering_prompt, send_to=send_to)

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

    # -- One-call event handling --

    async def react(self, event: str, state: MentalState, send_to: str | None = TASK) -> MentalState:
        """Analyze an event and apply the resulting impact to a new state.

        Convenience over ``observe`` + ``MentalState.apply``. Returns a NEW
        MentalState; the input state is untouched.

        Args:
            event: The event text to react to.
            state: Current psychological state.
            send_to: Routing group for LLM calls (TASK/SMOL/TINY/SLOW/PLAN).

        Returns:
            New MentalState with the event applied.
        """
        impact = await self.observe(event, state, send_to=send_to)
        return state.apply(impact)

    async def extract_style(
        self,
        character_name: str,
        dialogues: list[str],
        send_to: str | None = TASK,
    ) -> LinguisticStyle:
        """Extract linguistic style from character dialogues via LLM.

        Args:
            character_name: The character's name.
            dialogues: List of dialogue strings from the character.
            send_to: Routing group for LLM calls (TASK/SMOL/TINY/SLOW/PLAN).

        Returns:
            Extracted LinguisticStyle.
        """
        prompt = TEMPLATE_MANAGER.render_template(
            character_config.mind_style_extraction_template,
            {"character_name": character_name, "dialogues": dialogues},
        )
        return await self.propose(LinguisticStyle, prompt, send_to=send_to)
