from asyncio import Queue
from typing import Iterable, Any, Dict, Self, List

import litellm
from litellm.types.utils import StreamingChoices, ModelResponse, Choices
from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    NonNegativeInt,
    ConfigDict,
    HttpUrl,
    SecretStr,
    NonNegativeFloat,
    PrivateAttr,
)

from fabricatio.config import configs
from fabricatio.models.utils import Messages


class Base(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)


class WithToDo(Base):
    _todo: Queue[str] = PrivateAttr(default_factory=Queue)
    """
    The todo list of the current instance.
    """

    async def add_todo(self, todo_msg: str) -> Self:
        """
        Add a todo item to the todo list.
        Args:
            todo_msg: The todo item to be added to the todo list.

        Returns:
            Self: The current instance object to support method chaining.
        """

        await self._todo.put(todo_msg)
        return self

    async def get_todo(self) -> str:
        """
        Get the last todo item from the todo list.
        Returns:
            str: The last todo item from the todo list.

        """
        # Pop the last todo item from the todo list
        return await self._todo.get()


class Named(Base):
    name: str = Field(frozen=True)
    """
    Name of the object.
    """


class Described(Base):
    description: str = Field(default="", frozen=True)
    """
    Description of the object.
    """


class WithBriefing(Named, Described):

    @property
    def briefing(self) -> str:
        """
        Get the briefing of the object.
        Returns:
            str: The briefing of the object.
        """
        return f"{self.name}: {self.description}" if self.description else self.name


class Memorable(Base):
    memory: List[str] = Field(default_factory=list)
    """
    Memory list.
    """
    memory_max_size: NonNegativeInt = Field(default=0)
    """
    Maximum size of the memory list.
    """

    def add_memory(self, memories: str | Iterable[str]) -> Self:
        """
        Add memory items to the memory list.

        This method appends memory items to the memory list of the current instance.

        Parameters:
        - memories: str | Iterable[str] - A single memory item as a string or multiple memory items as an iterable.

        Returns:
        - Returns the current instance object to support method chaining.

        This method design allows users to add memory items to the memory list
        through a unified interface, enhancing code usability and extensibility.
        """
        # Convert a single memory item to a list
        if isinstance(memories, str):
            memories = [memories]
        # Add memory items to the memory list
        self.memory.extend(memories)
        # Limit the memory list size if the maximum size is set
        if self.memory_max_size > 0:
            self.memory = self.memory[-self.memory_max_size:]
        # Return the current instance object to support method chaining
        return self

    def top_memories(self, n: PositiveInt = 1) -> List[str]:
        """
        Get the top memory items from the memory list.

        This method returns the top memory items from the memory list of the current instance.

        Parameters:
        - n: PositiveInt - The number of top memory items to return.

        Returns:
        - List[str] - The top memory items from the memory list.

        This method design allows users to get the top memory items from the memory list
        through a unified interface, enhancing code usability and extensibility.
        """
        # Get the top memory items from the memory list
        return self.memory[-n:]

    def top_memories_as_string(self, n: PositiveInt = 1, separator: str = "\n\n") -> str:
        """
        Get the memory items as a string.

        This method returns the memory items as a string from the memory list of the current instance.

        Parameters:
        - n: PositiveInt - The number of memory items to return.
        - separator: str - The separator to join memory items.

        Returns:
        - str - The memory items as a string.

        This method design allows users to get the memory items as a string from the memory list
        through a unified interface, enhancing code usability and extensibility.
        """
        # Get the top memory items from the memory list
        memories = self.top_memories(n)
        # Join memory items with the separator
        return separator.join(memories)

    def clear_memories(self) -> Self:
        """
        Clear all memory items.

        This method clears all memory items from the memory list of the current instance.

        Parameters:
        - self: The current instance object.

        Returns:
        - Returns the current instance object to support method chaining.

        This method design allows users to clear all memory items from the memory list
        through a unified interface, enhancing code usability and extensibility.
        """
        # Clear all memory items from the memory list
        self.memory.clear()
        # Return the current instance object to support method chaining
        return self


class LLMUsage(Base):
    llm_api_endpoint: HttpUrl = Field(default=configs.llm.api_endpoint)
    """
    The OpenAI API endpoint.
    """

    llm_api_key: SecretStr = Field(default=configs.llm.api_key)
    """
    The OpenAI API key.
    """

    llm_timeout: PositiveInt = Field(default=configs.llm.timeout)
    """
    The timeout of the LLM model.
    """

    llm_max_retries: PositiveInt = Field(default=configs.llm.max_retries)
    """
    The maximum number of retries.
    """

    llm_model: str = Field(default=configs.llm.model)
    """
    The LLM model name.
    """

    llm_temperature: NonNegativeFloat = Field(default=configs.llm.temperature)
    """
    The temperature of the LLM model.
    """

    llm_stop_sign: str = Field(default=configs.llm.stop_sign)
    """
    The stop sign of the LLM model.
    """

    llm_top_p: NonNegativeFloat = Field(default=configs.llm.top_p)
    """
    The top p of the LLM model.
    """

    llm_generation_count: PositiveInt = Field(default=configs.llm.generation_count)
    """
    The number of generations to generate.
    """

    llm_stream: bool = Field(default=configs.llm.stream)
    """
    Whether to stream the LLM model's response.
    """

    llm_max_tokens: PositiveInt = Field(default=configs.llm.max_tokens)
    """
    The maximum number of tokens to generate.
    """

    def model_post_init(self, __context: Any) -> None:
        litellm.api_key = self.llm_api_key.get_secret_value()
        litellm.api_base = self.llm_api_endpoint.unicode_string()

    async def aquery(
            self,
            messages: List[Dict[str, str]],
            model: str | None = None,
            temperature: NonNegativeFloat | None = None,
            stop: str | None = None,
            top_p: NonNegativeFloat | None = None,
            max_tokens: PositiveInt | None = None,
            n: PositiveInt | None = None,
            stream: bool | None = None,
            timeout: PositiveInt | None = None,
            max_retries: PositiveInt | None = None,
    ) -> ModelResponse:
        """
        Asynchronously queries the language model to generate a response based on the provided messages and parameters.

        Parameters:
        - messages (List[Dict[str, str]]): A list of messages, where each message is a dictionary containing the role and content of the message.
        - model (str | None): The name of the model to use. If not provided, the default model will be used.
        - temperature (NonNegativeFloat | None): Controls the randomness of the output. Lower values make the output more deterministic.
        - stop (str | None): A sequence at which to stop the generation of the response.
        - top_p (NonNegativeFloat | None): Controls the diversity of the output through nucleus sampling.
        - max_tokens (PositiveInt | None): The maximum number of tokens to generate in the response.
        - n (PositiveInt | None): The number of responses to generate.
        - stream (bool | None): Whether to receive the response in a streaming fashion.
        - timeout (PositiveInt | None): The timeout duration for the request.
        - max_retries (PositiveInt | None): The maximum number of retries in case of failure.

        Returns:
        - ModelResponse: An object containing the generated response and other metadata from the model.
        """
        # Call the underlying asynchronous completion function with the provided and default parameters
        return await litellm.acompletion(
            messages=messages,
            model=model or self.llm_model,
            temperature=temperature or self.llm_temperature,
            stop=stop or self.llm_stop_sign,
            top_p=top_p or self.llm_top_p,
            max_tokens=max_tokens or self.llm_max_tokens,
            n=n or self.llm_generation_count,
            stream=stream or self.llm_stream,
            timeout=timeout or self.llm_timeout,
            max_retries=max_retries or self.llm_max_retries,
        )

    async def aask(
            self,
            question: str,
            system_message: str = "",
            model: str | None = None,
            temperature: NonNegativeFloat | None = None,
            stop: str | None = None,
            top_p: NonNegativeFloat | None = None,
            max_tokens: PositiveInt | None = None,
            n: PositiveInt | None = None,
            stream: bool | None = None,
            timeout: PositiveInt | None = None,
            max_retries: PositiveInt | None = None,
    ) -> List[Choices | StreamingChoices]:
        return (
            await self.aquery(
                messages=Messages().add_system_message(system_message).add_user_message(question),
                model=model,
                temperature=temperature,
                stop=stop,
                top_p=top_p,
                max_tokens=max_tokens,
                n=n,
                stream=stream,
                timeout=timeout,
                max_retries=max_retries,
            )
        ).choices
