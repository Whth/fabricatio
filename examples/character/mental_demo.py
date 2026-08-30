"""Drive one character through a complete mental-state transition chain.

Seeds a ``MentalState`` from a ``CharacterCard``, reacts to three events via
``UseMind.react`` (observe + apply), and prints the psychology block a writing
LLM would receive from ``state.as_prompt()``.

All LLM calls follow the default ``TASK`` routing: they go to whatever
completion group your fabricatio config assigns to the running task. A full
run costs roughly 24 calls (~12k input / ~400 output tokens).

Run from the repository root:

    python examples/character/mental_demo.py
"""

import asyncio
from typing import TYPE_CHECKING

from fabricatio_character.capabilities.mental import UseMind
from fabricatio_character.models.character import CharacterCard

if TYPE_CHECKING:
    from fabricatio_character.models.mental import MentalState


class StoryTeller(UseMind):
    """Minimal agent: just the mental engine, nothing else."""


def card() -> CharacterCard:
    """Build the example character card."""
    return CharacterCard(
        name="Akino Ai",
        roles=["live-in girlfriend", "illustrator"],
        activated_role="live-in girlfriend",
        look="long black hair, brown eyes, baby face that clashes with her tall figure",
        act="sharp-tongued but soft-hearted; teases her boyfriend, then secretly blushes",
        want="to be remembered and taken seriously by her boyfriend",
        flaw="a mouth that never admits defeat; the more she cares, the more she lies through her teeth",
        where="a small apartment shared with her boyfriend",
        condition="22 years old, freelance illustrator, second year of cohabitation",
        mood="smug and pleased",
    )


async def main() -> None:
    """Onboard the character, react to three events, print the final prompt."""
    agent = StoryTeller()

    # 1. Card -> initial MentalState (LLM judges need level + distortion
    #    tendencies from `want`/`flaw`; 6 calls, all parallel).
    state: MentalState = await agent.seed_from(card(), age=22)
    print(f"seeded: need={state.needs.current_level.name} emotion={state.emotion.emotion.name}")

    # 2. One transition per event: observe() analyzes (4-8 calls), apply()
    #    evolves the state deterministically and returns a new instance.
    for event in (
        "He remembered the exhibition she mentioned once and bought two tickets.",
        "He didn't reply all night; turns out he passed out at a friend's place.",
        "He praised someone else's outfit in front of friends and called hers plain.",
    ):
        state = await agent.react(event, state)
        bias = state.emotion.active_distortion.name if state.emotion.active_distortion else "-"
        print(
            f"event: {event}\n"
            f"  need={state.needs.current_level.name} emotion={state.emotion.emotion.name}"
            f"({state.emotion.intensity:.0f}) bias={bias}"
            f" traumas={len(state.sufferings)}"
        )

    # 3. The psychology block injected as system context for in-character writing.
    print(state.as_prompt())


if __name__ == "__main__":
    asyncio.run(main())
