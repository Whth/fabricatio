"""This module contains the capabilities for the thinking."""

from abc import ABC
from itertools import count
from typing import Optional

from fabricatio_core import logger
from fabricatio_core.capabilities.propose import Propose

from fabricatio_thinking.models.thinking import Thought
from fabricatio_thinking.rust import ThoughtVCS


class Thinking(Propose, ABC):
    """This class contains the capabilities for the thinking."""

    async def thinking(
        self, question: str, vcs: Optional[ThoughtVCS] = None, max_steps: Optional[int] = 25, **kwargs
    ) -> ThoughtVCS:
        """Perform a step-by-step thinking process to address the given question.

        This method iteratively generates thoughts using the LLM, commits them to version
        control, revises previous thoughts if needed, and checks out branches based on the
        thought process. The loop continues until a maximum number of steps is reached or
        the end of the thinking process is signaled.

        Args:
            question (str): The input question or task to be processed.
            vcs (Optional[ThoughtVCS]): An optional ThoughtVCS instance for managing
                version-controlled thoughts. If not provided, a new instance will be created.
            max_steps (Optional[int]): The maximum number of thinking steps to perform.
                If not specified, an effectively infinite number of steps will be allowed.
            **kwargs: Additional keyword arguments passed to the underlying propose method.

        Returns:
            ThoughtVCS: The final state of the ThoughtVCS after completing the thinking
                process.
        """
        vcs = vcs or ThoughtVCS()
        logger.debug("Initialized ThoughtVCS")

        for step in count():
            thought = await self.propose(Thought, question, **kwargs)
            logger.debug(f"Step {step}: Received thought - {thought}")

            # Commit the current thought
            logger.debug(f"Committing thought: {thought.serial} - {thought.thought}")
            vcs.commit(
                content=thought.thought, serial=thought.serial, estimated=thought.estimated, branch=thought.branch
            )

            # Revise if needed
            if thought.revision and thought.revises_thought is not None:
                logger.debug(f"Revising thought: {thought.revises_thought} with new content: {thought.thought}")
                vcs.revise(content=thought.thought, serial=thought.revises_thought, branch=thought.branch)

            # Checkout (branch) if needed
            if thought.checkout is not None and thought.branch is not None:
                logger.debug(f"Checking out branch: {thought.branch} at serial: {thought.checkout}")
                vcs.checkout(branch=thought.branch, serial=thought.checkout)

            if thought.end or (max_steps and step >= max_steps):
                logger.debug("End of thinking process reached.")
                break

        logger.debug("Returning final VCS state")
        return vcs
