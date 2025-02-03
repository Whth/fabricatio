from typing import List

from pydantic import Field

from fabricatio.models.generic import Named, Memorable, Described, WithToDo


class Role(Named, Memorable, Described, WithToDo):
    actions: List[str] = Field()
