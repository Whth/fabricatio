"""A module containing the RAG (Retrieval-Augmented Generation) models."""

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List

from fabricatio.decorators import precheck_package
from pydantic import BaseModel, ConfigDict, JsonValue

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo
    from pymilvus import CollectionSchema


class MilvusDataBase(BaseModel, metaclass=ABCMeta):
    """A base class for Milvus data."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    primary_field_name: ClassVar[str] = "id"

    vector_field_name: ClassVar[str] = "vector"

    def prepare_insertion(self, vector: List[float]) -> Dict[str, Any]:
        """Prepares the data for insertion into Milvus.

        Returns:
            dict: A dictionary containing the data to be inserted into Milvus.
        """
        return {**self.model_dump(exclude_none=True, by_alias=True), self.vector_field_name: vector}

    @property
    @abstractmethod
    def to_vectorize(self) -> str:
        """The text representation of the data."""

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
