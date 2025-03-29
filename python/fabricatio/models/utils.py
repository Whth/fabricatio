"""A module containing utility classes for the models."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Self

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    """A class representing a message."""

    model_config = ConfigDict(use_attribute_docstrings=True)
    role: Literal["user", "system", "assistant"]
    """
    Who is sending the message.
    """
    content: str
    """
    The content of the message.
    """


class Messages(list):
    """A list of messages."""

    def add_message(self, role: Literal["user", "system", "assistant"], content: str) -> Self:
        """Adds a message to the list with the specified role and content.

        Args:
            role (Literal["user", "system", "assistant"]): The role of the message sender.
            content (str): The content of the message.

        Returns:
            Self: The current instance of Messages to allow method chaining.
        """
        if content:
            self.append(Message(role=role, content=content))
        return self

    def add_user_message(self, content: str) -> Self:
        """Adds a user message to the list with the specified content.

        Args:
            content (str): The content of the user message.

        Returns:
            Self: The current instance of Messages to allow method chaining.
        """
        return self.add_message("user", content)

    def add_system_message(self, content: str) -> Self:
        """Adds a system message to the list with the specified content.

        Args:
            content (str): The content of the system message.

        Returns:
            Self: The current instance of Messages to allow method chaining.
        """
        return self.add_message("system", content)

    def add_assistant_message(self, content: str) -> Self:
        """Adds an assistant message to the list with the specified content.

        Args:
            content (str): The content of the assistant message.

        Returns:
            Self: The current instance of Messages to allow method chaining.
        """
        return self.add_message("assistant", content)

    def as_list(self) -> List[Dict[str, str]]:
        """Converts the messages to a list of dictionaries.

        Returns:
            list[dict]: A list of dictionaries representing the messages.
        """
        return [message.model_dump() for message in self]


class MilvusData(BaseModel):
    """A class representing data stored in Milvus."""

    model_config = ConfigDict(use_attribute_docstrings=True)
    id: Optional[int] = Field(default=None)
    """The identifier of the data."""

    vector: List[float]
    """The vector representation of the data."""

    text: str
    """The text representation of the data."""

    subject: Optional[str] = Field(default=None)
    """A subject label that we use to demo metadata filtering later."""

    def prepare_insertion(self) -> Dict[str, Any]:
        """Prepares the data for insertion into Milvus.

        Returns:
            dict: A dictionary containing the data to be inserted into Milvus.
        """
        return self.model_dump(exclude_none=True)

    def update_subject(self, new_subject: str) -> Self:
        """Updates the subject label of the data.

        Args:
            new_subject (str): The new subject label.

        Returns:
            Self: The updated instance of MilvusData.
        """
        self.subject = new_subject
        return self

    def update_id(self, new_id: int) -> Self:
        """Updates the identifier of the data.

        Args:
            new_id (int): The new identifier.

        Returns:
            Self: The updated instance of MilvusData.
        """
        self.id = new_id
        return self


class TaskStatus(Enum):
    """An enumeration representing the status of a task.

    Attributes:
        Pending: The task is pending.
        Running: The task is currently running.
        Finished: The task has been successfully completed.
        Failed: The task has failed.
        Cancelled: The task has been cancelled.
    """

    Pending = "pending"
    Running = "running"
    Finished = "finished"
    Failed = "failed"
    Cancelled = "cancelled"


