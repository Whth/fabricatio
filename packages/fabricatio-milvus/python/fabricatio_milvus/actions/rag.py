"""Inject data into the database."""

from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action
from fabricatio_core.rust import CONFIG
from fabricatio_core.utils import ok

from fabricatio_milvus.capabilities.milvus import AddConfig, MilvusRAG
from fabricatio_milvus.config import milvus_config
from fabricatio_milvus.models.milvus import MilvusDataBase


class InjectToDB(Action, MilvusRAG):
    """Inject data into the database."""

    output_key: str = "collection_name"
    collection_name: str = "my_collection"
    """The name of the collection to inject data into."""

    async def _execute[T: MilvusDataBase](
        self,
        to_inject: T | list[T | None] | None,
        override_inject: bool = False,
        **_,
    ) -> str | None:
        from pymilvus.milvus_client import IndexParams

        if to_inject is None:
            return None
        if not isinstance(to_inject, list):
            to_inject = [to_inject]
        if not (seq := [t for t in to_inject if t is not None]):  # filter out None
            return None
        logger.info(f"Injecting {len(seq)} items into the collection '{self.collection_name}'")
        if override_inject:
            self.client.drop_collection(self.collection_name)

        dimension = ok(
            self.milvus_dimensions or milvus_config.milvus_dimensions or self.embedding_ndim or CONFIG.embedding.ndim,
        )
        if not self.client.has_collection(self.collection_name):
            self.client.create_collection(
                self.collection_name,
                auto_id=True,
                dimension=dimension,
                schema=seq[0].as_milvus_schema(dimension),
                index_params=IndexParams(
                    seq[0].vector_field_name,
                    index_name=seq[0].vector_field_name,
                    index_type=seq[0].index_type,
                    metric_type=seq[0].metric_type,
                ),
            )
        await self.add_document(seq, AddConfig(collection_name=self.collection_name, flush=True))

        return self.collection_name
