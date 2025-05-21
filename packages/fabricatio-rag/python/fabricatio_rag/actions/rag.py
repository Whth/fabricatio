"""Inject data into the database."""

from typing import List, Optional

from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action
from fabricatio_core.models.task import Task
from fabricatio_core.rust import CONFIG
from fabricatio_core.utils import ok

from fabricatio_rag.capabilities.rag import RAG
from fabricatio_rag.models.rag import MilvusClassicModel, MilvusDataBase


class InjectToDB(Action, RAG):
    """Inject data into the database."""

    output_key: str = "collection_name"
    collection_name: str = "my_collection"
    """The name of the collection to inject data into."""

    async def _execute[T: MilvusDataBase](
        self, to_inject: Optional[T] | List[Optional[T]], override_inject: bool = False, **_
    ) -> Optional[str]:
        from pymilvus.milvus_client import IndexParams

        if to_inject is None:
            return None
        if not isinstance(to_inject, list):
            to_inject = [to_inject]
        if not (seq := [t for t in to_inject if t is not None]):  # filter out None
            return None
        logger.info(f"Injecting {len(seq)} items into the collection '{self.collection_name}'")
        if override_inject:
            self.check_client().client.drop_collection(self.collection_name)

        await self.view(
            self.collection_name,
            create=True,
            schema=seq[0].as_milvus_schema(
                ok(
                    self.milvus_dimensions
                    or CONFIG.rag.milvus_dimensions
                    or self.embedding_dimensions
                    or CONFIG.embedding.dimensions
                ),
            ),
            index_params=IndexParams(
                seq[0].vector_field_name,
                index_name=seq[0].vector_field_name,
                index_type=seq[0].index_type,
                metric_type=seq[0].metric_type,
            ),
        ).add_document(seq, flush=True)

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
        from questionary import text

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
