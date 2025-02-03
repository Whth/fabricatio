from abc import abstractmethod

from fabricatio.models.generic import WithBriefing


class Action(WithBriefing):
    pass

    @abstractmethod
    async def execute(self, *args, **kwargs):
        pass
