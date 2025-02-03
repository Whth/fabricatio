from typing import List, Iterable

from pydantic import BaseModel, Field

from fabricatio.models.generic import M


class WithToDo(BaseModel):
    todo: List[str] = Field(default_factory=list, description="Todo")

    def add_todos(self: M, todos: str | Iterable[str]) -> M:
        """
        Adds todo items to the current instance.

        This method allows adding a single todo item as a string or multiple todo items
        as a collection (e.g., list, tuple) to the instance's todo list. If a single todo
        item (string) is provided, it is appended to the end of the todo list. If a collection
        of todo items is provided, all items are extended into the todo list.

        Parameters:
        - self: The current instance object.
        - todos: The todo items to add, which can be a single string or a collection of strings.

        Returns:
        - Returns the current instance object to support method chaining.

        This method design allows users to flexibly add todo items, whether single or multiple,
        through a unified interface, enhancing code usability and extensibility.
        """
        # Determine the type of todos to decide between append and extend methods
        if isinstance(todos, str):
            # If todos is a string, append it to the todo list
            self.todo.append(todos)
        else:
            # If todos is a collection of strings, extend all elements to the todo list
            self.todo.extend(todos)
        # Return the current instance object to support method chaining
        return self

    def clear_todos(self: M) -> M:
        """
        Clear all todo items.

        This method clears all todo items from the todo list of the current instance.

        Parameters:
        - self: The current instance object.

        Returns:
        - Returns the current instance object to support method chaining.

        This method design allows users to clear all todo items from the todo list
        through a unified interface, enhancing code usability and extensibility.
        """
        # Clear all todo items from the todo list
        self.todo.clear()
        # Return the current instance object to support method chaining
        return self
