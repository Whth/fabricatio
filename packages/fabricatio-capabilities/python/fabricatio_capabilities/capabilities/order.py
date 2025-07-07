from typing import List

from fabricatio_capabilities.capabilities.rating import Rating
from fabricatio_core.models.generic import WithBriefing


class Ordering(Rating):

    async def order_strings(self,seq:List[str],requirement:str,**kwargs)->List[str]:
        ...


    async def fast_order(self,seq:List[str]|List[WithBriefing],requirement:str,**kwargs)->List[str]|List[WithBriefing]:
        ...

    async def order(self,seq:List[str]|List[WithBriefing],requirement:str,**kwargs)->List[str]|List[WithBriefing]:
        ...