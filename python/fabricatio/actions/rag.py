"""Inject data into the database."""

from typing import List, Optional, Unpack

from fabricatio.capabilities.rag import RAG
from fabricatio.models.action import Action
from fabricatio.models.generic import PrepareVectorization


class InjectToDB(Action, RAG):
    """Inject data into the database."""

    output_key: str = "collection_name"

    async def _execute[T: PrepareVectorization](
        self, to_inject: T | List[T], collection_name: Optional[str] = "my_collection", **cxt: Unpack
    ) -> str:
        if not isinstance(to_inject, list):
            to_inject = [to_inject]

        await self.view(collection_name, create=True).consume_string(
            [t.prepare_vectorization(self.embedding_max_sequence_length) for t in to_inject],
        )

        return collection_name
