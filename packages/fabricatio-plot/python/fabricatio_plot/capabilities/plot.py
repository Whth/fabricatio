from typing import Unpack

from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs


class Plot(Propose):


    async def plot(self,requirement:str,**kwargs:Unpack[ValidateKwargs[str]]):
        
        source = await self.acode_string(requirement, "python",**kwargs)
    