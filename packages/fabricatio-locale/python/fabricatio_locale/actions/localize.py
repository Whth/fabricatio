"""Module containing the LocalizePoFile action for localizing .po files."""

from pathlib import Path
from typing import Any, ClassVar, Optional

from fabricatio_core import Action

from fabricatio_locale.capabilities.localize import Localize
from fabricatio_locale.rust import read_pofile, update_pofile


class LocalizePoFile(Action, Localize):
    """Action class to localize messages in a .po file."""

    ctx_override: ClassVar[bool] = True

    pofile: str | Path = "file.po"
    """Path to the source .po file containing messages to localize."""

    target_lang: str = "en"
    """Target language code (e.g., 'es' for Spanish) to translate messages into."""

    output_path: Optional[str | Path] = "locale_file.po"
    """Optional path to save the updated .po file. Defaults to same as input if not specified."""

    async def _execute(self, *_: Any, **cxt: Any) -> Path:
        """Localizes messages in the .po file and updates it with translations.

        Reads the .po file, localizes the messages using the configured target language,
        and writes the translated messages back to the output file.

        Args:
            *_: Positional arguments (ignored).
            **cxt: Contextual keyword arguments (ignored).

        Returns:
            Path: The path to the updated .po file containing localized messages.
        """
        msgs = read_pofile(self.pofile)
        translated_msgs = await self.localize(msgs, target_language=self.target_lang)
        out = self.output_path or self.pofile
        update_pofile(out, translated_msgs)

        return Path(out)
