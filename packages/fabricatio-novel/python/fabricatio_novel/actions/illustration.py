"""Illustration specialization of the staged dump: every scene is drawn before the export."""

from pathlib import Path
from typing import Any

from fabricatio_core.rust import SMOL

from fabricatio_novel.actions.novel import DumpNovelStage
from fabricatio_novel.capabilities.illustration import IllustrateScenes
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import ExportFormat, Novel

__all__ = ["IllustrateNovelStage"]


class IllustrateNovelStage(DumpNovelStage, IllustrateScenes):
    """Dump action of the illustrated pipeline: its post-process hook draws every scene first.

    ``post_process_novel`` resolves to :meth:`IllustrateScenes.post_process_novel`, whose
    signature declares ``persist_dir``, ``send_to`` and the illustration knobs, so this action
    declares them too and passes them on; the plain :class:`DumpNovelStage` calls the same hook
    with the base interface's arguments alone.
    """

    async def _execute(  # noqa: PLR0913 - one parameter per task init context key, as the context is unpacked here
        self,
        novel_ctx: NovelContext,
        novel: Novel,
        *,
        persist_dir: Path,
        export_format: ExportFormat = ExportFormat.EPUB,
        output_path: str | None = None,
        font: str | Path | None = None,
        cover: str | Path | None = None,
        send_to: str | None = SMOL,
        illustration_choose_loras: bool | None = None,
        illustration_judge: bool | None = None,
        illustration_judge_max_tries: int | None = None,
        **_: Any,
    ) -> Path:
        """Illustrate every scene through the chain's hook, then export the JSON snapshot and the artifacts."""
        novel = await self.post_process_novel(
            novel_ctx,
            novel,
            persist_dir=persist_dir,
            send_to=send_to,
            illustration_choose_loras=illustration_choose_loras,
            illustration_judge=illustration_judge,
            illustration_judge_max_tries=illustration_judge_max_tries,
        )
        return self.export(
            novel, persist_dir, export_format=export_format, output_path=output_path, font=font, cover=cover
        )
