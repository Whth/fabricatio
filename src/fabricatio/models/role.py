from typing import Dict, Any

from pydantic import Field

from fabricatio.core import env
from fabricatio.models.action import WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.generic import Memorable, WithToDo, WithBriefing, LLMUsage


class Role(Memorable, WithBriefing, WithToDo, LLMUsage):

    registry: Dict[Event | str, WorkFlow] = Field(...)
    """ The registry of events and workflows."""

    def model_post_init(self, __context: Any) -> None:
        for event, workflow in self.registry.items():
            workflow.fallback_to(self)
            env.on(event, workflow.serve)
