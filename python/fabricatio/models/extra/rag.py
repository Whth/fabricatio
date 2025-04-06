"""A module containing the RAG (Retrieval-Augmented Generation) models."""

from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Self, Sequence

from fabricatio.decorators import precheck_package
from fabricatio.models.generic import Vectorizable
from pydantic import JsonValue

if TYPE_CHECKING:
    from importlib.util import find_spec

    from pydantic.fields import FieldInfo

    if find_spec("pymilvus"):
        from pymilvus import CollectionSchema


class MilvusDataBase(Vectorizable, ABC):
    """A base class for Milvus data."""

    primary_field_name: ClassVar[str] = "id"
    """The name of the primary field in Milvus."""
    vector_field_name: ClassVar[str] = "vector"
    """The name of the vector field in Milvus."""

    def prepare_insertion(self, vector: List[float]) -> Dict[str, Any]:
        """Prepares the data for insertion into Milvus.

        Returns:
            dict: A dictionary containing the data to be inserted into Milvus.
        """
        return {**self.model_dump(exclude_none=True, by_alias=True), self.vector_field_name: vector}

    @classmethod
    @precheck_package(
        "pymilvus", "pymilvus is not installed. Have you installed `fabricatio[rag]` instead of `fabricatio`?"
    )
    def as_milvus_schema(cls, dimension: int = 1024) -> "CollectionSchema":
        """Generates the schema for Milvus collection."""
        from pymilvus import CollectionSchema, DataType, FieldSchema

        fields = [
            FieldSchema(cls.primary_field_name, dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(cls.vector_field_name, dtype=DataType.FLOAT_VECTOR, dim=dimension),
        ]

        type_mapping = {
            str: DataType.STRING,
            int: DataType.INT64,
            float: DataType.DOUBLE,
            JsonValue: DataType.JSON,
            # TODO add more mapping
        }

        for k, v in cls.model_fields.items():
            k: str
            v: FieldInfo
            fields.append(
                FieldSchema(k, dtype=type_mapping.get(v.annotation, DataType.UNKNOWN), description=v.description or "")
            )
        return CollectionSchema(fields)

    @classmethod
    def from_sequence(cls, data: Sequence[Dict[str, Any]]) -> List[Self]:
        """Constructs a list of instances from a sequence of dictionaries."""
        return [cls(**d) for d in data]



class MilvusClassicModel(MilvusDataBase):
    """A class representing a classic model stored in Milvus."""

    text: str
    """The text to be stored in Milvus."""
    subject: str=""
    """The subject of the text."""

    def _prepare_vectorization_inner(self) -> str:
        return self.text
