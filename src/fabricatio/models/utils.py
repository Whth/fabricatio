from typing import Literal, Self, List, Dict

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "system", "assistant"] = Field(default="user")
    """
    Who is sending the message.
    """
    content: str = Field(default="")
    """
    The content of the message.
    """


class Messages(list):
    """
    A list of messages.
    """

    def add_message(self, role: Literal["user", "system", "assistant"], content: str) -> Self:
        """
        Adds a message to the list with the specified role and content.

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
        """
        Adds a user message to the list with the specified content.

        Args:
            content (str): The content of the user message.

        Returns:
            Self: The current instance of Messages to allow method chaining.
        """
        return self.add_message("user", content)

    def add_system_message(self, content: str) -> Self:
        """
        Adds a system message to the list with the specified content.

        Args:
            content (str): The content of the system message.

        Returns:
            Self: The current instance of Messages to allow method chaining.
        """
        return self.add_message("system", content)

    def add_assistant_message(self, content: str) -> Self:
        """
        Adds an assistant message to the list with the specified content.

        Args:
            content (str): The content of the assistant message.

        Returns:
            Self: The current instance of Messages to allow method chaining.
        """
        return self.add_message("assistant", content)

    def as_list(self) -> List[Dict[str, str]]:
        """
        Converts the messages to a list of dictionaries.

        Returns:
            list[dict]: A list of dictionaries representing the messages.
        """
        return [message.dict() for message in self]
