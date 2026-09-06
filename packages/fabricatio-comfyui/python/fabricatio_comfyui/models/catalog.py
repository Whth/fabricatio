"""User-configured LoRA catalog with LLM-driven selection.

The catalog is the manual-config side: the user declares each LoRA once —
server-side filename, recommended strength, what it does, and the trigger
words that activate it — via ``[comfyui.loras]`` in the fabricatio config
chain (or programmatically).  The proposal side (:class:`LoraSelection`)
is what the LLM fills in: given the catalog brief, it picks entries by
name.  Resolution (:meth:`LoraCatalog.resolve`) validates the pick
loudly — an unknown name is a ``ValueError``, never a silently skipped
LoRA — and falls each strength back to the entry's recommendation.
"""

from fabricatio_core.models.generic import ProposedAble
from pydantic import BaseModel, ConfigDict, Field

from fabricatio_comfyui.models.graph import LoraSpec

__all__ = ["LoraCatalog", "LoraEntry", "LoraPick", "LoraSelection"]


class LoraEntry(BaseModel):
    """A user-declared LoRA available on the ComfyUI server."""

    model_config = ConfigDict(frozen=True)

    lora_name: str
    """LoRA filename on the server (e.g. ``"anime-detail.safetensors"``)."""

    strength: float = Field(default=0.8, ge=-1.0, le=2.0)
    """Recommended strength for both the model and CLIP branches."""

    effect: str
    """What this LoRA does to the image, in one sentence — the LLM reads this to choose."""

    trigger_words: str = ""
    """Comma-separated trigger keywords to append to the prompt when this LoRA is used."""

    def augmented_prompt(self, prompt: str) -> str:
        """Return *prompt* with this entry's trigger words appended (no-op when unset)."""
        if not self.trigger_words:
            return prompt
        return f"{prompt}, {self.trigger_words}"


class LoraCatalog(BaseModel):
    """An ordered set of user-declared LoRAs the LLM may choose from."""

    entries: list[LoraEntry] = Field(default_factory=list)
    """Declared LoRAs, most general first."""

    @classmethod
    def from_config(cls) -> "LoraCatalog":
        """Build a catalog from :data:`fabricatio_comfyui.config.comfyui_config.loras`."""
        from fabricatio_comfyui.config import comfyui_config

        return cls(entries=list(comfyui_config.loras))

    def entry(self, lora_name: str) -> LoraEntry:
        """Return the entry named *lora_name*; raises ``ValueError`` when unknown."""
        for entry in self.entries:
            if entry.lora_name == lora_name:
                return entry
        raise ValueError(f"Unknown LoRA {lora_name!r}; available: {[e.lora_name for e in self.entries]}")

    def brief(self) -> str:
        """Render the catalog as the selection brief the LLM reads."""
        lines = [f"- {e.lora_name} (recommended strength {e.strength}): {e.effect}" for e in self.entries]
        return "\n".join(lines)

    def resolve(self, picks: list["LoraPick"]) -> list[LoraSpec]:
        """Validate *picks* against the catalog and return wired :class:`LoraSpec` list.

        Strengths fall back to each entry's recommendation; unknown names
        and out-of-range strengths fail loudly.
        """
        return [
            LoraSpec(
                lora_name=p.lora_name,
                strength=p.strength if p.strength is not None else self.entry(p.lora_name).strength,
            )
            for p in picks
        ]

    def augment(self, prompt: str, loras: list[LoraSpec]) -> str:
        """Append the trigger words of every used entry to *prompt*."""
        for spec in loras:
            prompt = self.entry(spec.lora_name).augmented_prompt(prompt)
        return prompt


class LoraPick(BaseModel):
    """One LoRA the LLM chose, with an optional strength override."""

    lora_name: str
    """Exact ``lora_name`` copied from the catalog brief — never invented."""

    strength: float | None = Field(default=None, ge=-1.0, le=2.0)
    """Chosen strength; ``None`` uses the entry's recommended strength."""


class LoraSelection(ProposedAble):
    """LoRA selection proposal — the target of :meth:`fabricatio_core.capabilities.propose.Propose.propose`.

    Feed :meth:`LoraCatalog.brief` plus the image description to the LLM;
    it returns the entries that fit the subject.  An empty ``picks`` list
    means "no LoRA needed" and is a valid answer.
    """

    picks: list[LoraPick] = Field(default_factory=list)
    """Chosen LoRAs in application order (the chain order on the server)."""
