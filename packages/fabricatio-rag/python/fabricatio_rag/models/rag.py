"""A module containing the RAG (Retrieval-Augmented Generation) models."""

from abc import ABC
from functools import partial
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Self, Sequence, Set

from fabricatio_core.decorators import precheck_package
from fabricatio_core.models.generic import Base, ScopedConfig, Vectorizable
from fabricatio_core.utils import ok
from pydantic import Field, JsonValue, PositiveFloat, PositiveInt, SecretStr

if TYPE_CHECKING:
    from importlib.util import find_spec

    from pydantic.fields import FieldInfo

    if find_spec("pymilvus"):
        from pymilvus import CollectionSchema


class MilvusScopedConfig(ScopedConfig):
    """A class representing the configuration for Milvus."""

    milvus_uri: Optional[str] = Field(default=None)
    """The URI of the Milvus server."""

    milvus_token: Optional[SecretStr] = Field(default=None)
    """The token for the Milvus server."""

    milvus_timeout: Optional[PositiveFloat] = Field(default=None)
    """The timeout for the Milvus server."""

    milvus_dimensions: Optional[PositiveInt] = Field(default=None)
    """The dimensions of the Milvus server."""


class MilvusDataBase(Base, Vectorizable, ABC):
    """A base class for Milvus data."""

    primary_field_name: ClassVar[str] = "id"
    """The name of the primary field in Milvus."""
    vector_field_name: ClassVar[str] = "vector"
    """The name of the vector field in Milvus."""

    index_type: ClassVar[str] = "FLAT"
    """The type of index to be used in Milvus."""
    metric_type: ClassVar[str] = "COSINE"
    """The type of metric to be used in Milvus."""

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

        for k, v in cls.model_fields.items():
            k: str
            v: FieldInfo
            schema = partial(FieldSchema, k, description=v.description or "")
            anno = ok(v.annotation)

            if anno == int:
                fields.append(schema(dtype=DataType.INT64))
            elif anno == str:
                fields.append(schema(dtype=DataType.VARCHAR, max_length=65535))
            elif anno == float:
                fields.append(schema(dtype=DataType.DOUBLE))
            elif anno == list[str] or anno == List[str] or anno == set[str] or anno == Set[str]:
                fields.append(
                    schema(dtype=DataType.ARRAY, element_type=DataType.VARCHAR, max_length=65535, max_capacity=4096)
                )
            elif anno == list[int] or anno == List[int] or anno == set[int] or anno == Set[int]:
                fields.append(schema(dtype=DataType.ARRAY, element_type=DataType.INT64, max_capacity=4096))
            elif anno == list[float] or anno == List[float] or anno == set[float] or anno == Set[float]:
                fields.append(schema(dtype=DataType.ARRAY, element_type=DataType.DOUBLE, max_capacity=4096))
            elif anno == JsonValue:
                fields.append(schema(dtype=DataType.JSON))

            else:
                raise NotImplementedError(f"{k}:{anno} is not supported")

        return CollectionSchema(fields)

    @classmethod
    def from_sequence(cls, data: Sequence[Dict[str, Any]]) -> List[Self]:
        """Constructs a list of instances from a sequence of dictionaries."""
        return [cls(**d) for d in data]


class MilvusClassicModel(MilvusDataBase):
    """A class representing a classic model stored in Milvus."""

    text: str
    """The text to be stored in Milvus."""
    subject: str = ""
    """The subject of the text."""

    def _prepare_vectorization_inner(self) -> str:
        return self.text
