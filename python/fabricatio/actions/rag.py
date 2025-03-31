"""Inject data into the database."""

from typing import List, Optional

from questionary import text

from fabricatio.capabilities.rag import RAG
from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.generic import Vectorizable
from fabricatio.models.task import Task


class InjectToDB(Action, RAG):
    """Inject data into the database."""

    output_key: str = "collection_name"

    async def _execute[T: Vectorizable](
        self, to_inject: Optional[T] | List[Optional[T]], collection_name: str = "my_collection",override_inject:bool=False, **_
    ) -> Optional[str]:
        if not isinstance(to_inject, list):
            to_inject = [to_inject]
        logger.info(f"Injecting {len(to_inject)} items into the collection '{collection_name}'")
        if override_inject:
            self.check_client().client.drop_collection(collection_name)
        await self.view(collection_name, create=True).consume_string(
            [
                t.prepare_vectorization(self.embedding_max_sequence_length)
                for t in to_inject
                if isinstance(t, Vectorizable)
            ],
        )

        return collection_name


class RAGTalk(Action, RAG):
    """RAG-enabled conversational action that processes user questions based on a given task.

    This action establishes an interactive conversation loop where it retrieves context-relevant
    information to answer user queries according to the assigned task briefing.

    Notes:
        task_input: Task briefing that guides how to respond to user questions
        collection_name: Name of the vector collection to use for retrieval (default: "my_collection")

    Returns:
        Number of conversation turns completed before termination
    """

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **kwargs) -> int:
        collection_name = kwargs.get("collection_name", "my_collection")
        counter = 0

        self.view(collection_name, create=True)

        try:
            while True:
                user_say = await text("User: ").ask_async()
                if user_say is None:
                    break
                gpt_say = await self.aask_retrieved(
                    user_say,
                    user_say,
                    extra_system_message=f"You have to answer to user obeying task assigned to you:\n{task_input.briefing}",
                )
                print(f"GPT: {gpt_say}")  # noqa: T201
                counter += 1
        except KeyboardInterrupt:
            logger.info(f"executed talk action {counter} times")
        return counter
