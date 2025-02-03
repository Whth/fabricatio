from pydantic import Field

from fabricatio.models.generic import Named, Memorable, Described


class Action(Named, Memorable, Described):
    role: str = Field(default="", description="Role Name")
