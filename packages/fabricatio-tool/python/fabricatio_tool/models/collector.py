"""Module for the ResultCollector class, which is used to collect, submit, revoke, and retrieve results in a container."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Self, Type, overload

from fabricatio_core import logger


@dataclass
class ResultCollector:
    """Used for collecting results as the task requests.

    use .submit(key: str, val: Any) submit a result value `val` with the to the `key` slot.
    use .revoke(key: str) revoke a result from the container by its source `key`.
    """

    container: Dict[str, Any] = field(default_factory=dict)
    """A dictionary to store results."""

    def submit(self, key: str, val: Any) -> Self:
        """Submit a result to the container with the specified key.

        Args:
            key (str): The key to store the result under.
            val (Any): The result to store in the container.

        Returns:
            Self: The current instance for method chaining.
        """
        self.container[key] = val
        return self

    def revoke(self, key: str) -> Self:
        """Remove a result from the container by its source key.

        Args:
            key (str): The key of the result to remove.

        Returns:
            Self: The current instance for method chaining.

        Raises:
            KeyError: If the key is not found in the container.
        """
        if key in self.container:
            self.container.pop(key)
            return self
        logger.warn(f"Key '{key}' not found in container.")
        return self

    @overload
    def take[T](self, key: str, desired: Optional[Type[T]] = None) -> T | None: ...

    @overload
    def take[T](self, key: List[str], desired: Optional[Type[T]] = None) -> List[T | None]: ...

    def take[T](self, key: str | List[str], desired: Optional[Type[T]] = None) -> T | None | List[T | None]:
        """Retrieve value(s) from the container by key(s) with optional type checking.

        This method retrieves a single value or multiple values from the container based on the provided key(s).
        It supports optional type checking to ensure the retrieved value matches the expected type.

        Args:
            key (str | List[str]): A single key as a string or a list of keys to retrieve values for.
            desired (Optional[Type[T]]): The expected type of the retrieved value(s). If provided,
                type checking will be performed and None will be returned for mismatched types.

        Returns:
            T | None | List[T | None]: If key is a string, returns the value of type T or None.
                If key is a list, returns a list of values of type T or None for each key.
        """
        if isinstance(key, str):
            result = self.container.get(key)
            if desired is not None and result is not None and not isinstance(result, desired):
                logger.error(f"Type mismatch: expected {desired.__name__}, got {type(result).__name__}")
                return None
            return result
        results = []
        for k in key:
            result = self.container.get(k)
            if desired is not None and result is not None and not isinstance(result, desired):
                logger.error(f"Type mismatch for key '{k}': expected {desired.__name__}, got {type(result).__name__}")
                results.append(None)
            else:
                results.append(result)
        return results
