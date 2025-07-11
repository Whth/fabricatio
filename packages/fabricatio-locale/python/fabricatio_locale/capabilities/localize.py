"""Implements localization functionality by leveraging the translation mechanism."""

from typing import List, Unpack

from fabricatio_core.utils import ok
from fabricatio_translate.capabilities.translate import Translate
from fabricatio_translate.models.kwargs_types import TranslateKwargs

from fabricatio_locale.rust import Msg


class Localize(Translate):
    """A class that extends Translate to provide localization capabilities.

    This class handles the localization process by translating message texts
    while preserving message identifiers.
    """

    async def localize(self, msgs: List[Msg], **kwargs: Unpack[TranslateKwargs]) -> List[Msg]:
        """Localizes a list of messages by translating their text content.

        Args:
            msgs: A list of Message objects to be localized
            **kwargs: Additional keyword arguments for translation

        Returns:
            A list of localized Message objects with translated texts,
            but retaining original message IDs
        """
        translated_msg_txt_seq = ok(await self.translate([msg.txt for msg in msgs], **kwargs))
        return [
            Msg(txt=translated_msg_txt or msg.txt, id=msg.id)
            for translated_msg_txt, msg in zip(translated_msg_txt_seq, msgs, strict=True)
        ]
