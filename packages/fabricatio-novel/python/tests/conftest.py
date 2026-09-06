"""Make sibling helper modules (e.g. ``_support``) importable under any pytest import mode.

``--import-mode=importlib`` does not put the tests directory on ``sys.path``,
so bare imports of local helpers would fail without this.
"""

import sys
from pathlib import Path

import pytest
from fabricatio_comfyui.models import LoraCatalog
from fabricatio_novel.config import NovelConfig, novel_config

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(autouse=True)
def hermetic_loras(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep TOML LoRA state out of the mock-router tests.

    Catalog selection is opt-in per test: re-stub ``LoraCatalog.from_config``
    with a populated catalog and push a ``LoraSelection`` value onto the
    router stack.  The always-on chain is opt-in the same way: re-patch
    ``novel_config`` with a populated ``illustration_always_loras``.
    """
    monkeypatch.setattr(LoraCatalog, "from_config", classmethod(lambda cls: cls(entries=[])))
    monkeypatch.setattr(
        "fabricatio_novel.capabilities.illustration.novel_config",
        NovelConfig.model_validate({**novel_config.model_dump(), "illustration_always_loras": []}),
    )
