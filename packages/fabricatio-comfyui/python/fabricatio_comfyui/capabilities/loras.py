"""LLM-driven LoRA selection capability.

Mix ``ChooseLoras`` into a Role (alongside :class:`UseComfyUI`) to let
the LLM pick LoRAs for a generation from the user-declared catalog —
never inventing filenames: :meth:`LoraCatalog.resolve` raises on any
name absent from the catalog.  Manual config stays in charge of *what
exists*; the LLM only chooses among declared entries (or none).
"""

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.journal import logger

from fabricatio_comfyui.capabilities.comfyui import UseComfyUI
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.models.catalog import LoraCatalog, LoraSelection
from fabricatio_comfyui.models.graph import LoraSpec

__all__ = ["ChooseLoras"]


class ChooseLoras(Propose, UseComfyUI):
    """Capability mixin: choose LoRAs for an image description from the catalog."""

    async def choose_loras(
        self,
        description: str,
        *,
        catalog: LoraCatalog | None = None,
        send_to: str | None = None,
    ) -> list[LoraSpec]:
        """Let the LLM pick catalog LoRAs suited to *description*.

        Args:
            description: The image subject/scene the LoRAs should serve.
            catalog: Explicit catalog; ``None`` builds one from
                :data:`fabricatio_comfyui.config.comfyui_config.loras`.
            send_to: Routing group for the selection proposal; ``None`` keeps the global default group.

        Returns:
            Wired :class:`LoraSpec` list in chain order; empty when the
            catalog is undeclared or the LLM picks nothing.
        """
        cat = catalog if catalog is not None else LoraCatalog.from_config()
        if not cat.entries:
            return []
        selection = await self.propose(
            LoraSelection,
            TEMPLATE_MANAGER.render_template(
                comfyui_config.choose_loras_template,
                {"lora_catalog": cat.brief(), "image_description": description},
            ),
            send_to=send_to,
        )
        if not isinstance(selection, LoraSelection):
            logger.debug(f"LoRA selection for {description!r} produced no valid proposal")
            return []
        loras = cat.resolve(selection.picks)
        logger.debug(f"Chosen LoRAs for {description!r}: {[(spec.lora_name, spec.strength) for spec in loras]}")
        return loras
