from typing import List

from pydantic import Field

from fabricatio.models.generic import Named, Memorable, Described


class Role(Named, Memorable, Described):
    todo: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
