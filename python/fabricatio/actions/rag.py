"""Inject data into the database."""

from typing import List, Optional

from questionary import text

from fabricatio.capabilities.rag import RAG
from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.extra.rag import MilvusClassicModel, MilvusDataBase
from fabricatio.models.task import Task


class InjectToDB(Action, RAG):
    """Inject data into the database."""

    output_key: str = "collection_name"
    collection_name: str = "my_collection"
    """The name of the collection to inject data into."""

    async def _execute[T: MilvusDataBase](
        self, to_inject: Optional[T] | List[Optional[T]], override_inject: bool = False, **_
    ) -> Optional[str]:
        if to_inject is None:
            return None
        if not isinstance(to_inject, list):
            to_inject = [to_inject]
        logger.info(f"Injecting {len(to_inject)} items into the collection '{self.collection_name}'")
        if override_inject:
            self.check_client().client.drop_collection(self.collection_name)

        await self.view(self.collection_name, create=True).add_document(
            [t for t in to_inject if t is not None], flush=True
        )

        return self.collection_name


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
                ret: List[MilvusClassicModel] = await self.aretrieve(user_say, document_model=MilvusClassicModel)

                gpt_say = await self.aask(
                    user_say, system_message="\n".join(m.text for m in ret) + "\nYou can refer facts provided above."
                )
                print(f"GPT: {gpt_say}")  # noqa: T201
                counter += 1
        except KeyboardInterrupt:
            logger.info(f"executed talk action {counter} times")
        return counter
