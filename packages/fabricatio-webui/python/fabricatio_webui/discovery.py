"""Ecosystem-wide discovery of installed ``fabricatio-*`` packages.

The environment may contain any number of ecosystem packages —
``fabricatio-novel``, ``fabricatio-anki``, third-party extensions, … — so the
webui never hardcodes who owns workflows or actions: it scans every installed
distribution whose normalized name starts with ``fabricatio_``.
"""

import pkgutil
from importlib import metadata
from typing import List

#: Module name of this package; pinned first so its no-LLM "Hello Fabricatio"
#: demo always tops the blueprint rail.
_SELF = "fabricatio_webui"


def installed_fabricatio_packages() -> List[str]:
    """Return module names of every installed ``fabricatio_*`` package.

    The result unions import-distribution metadata with top-level package
    modules on ``sys.path``, covering editable installs and exotic layouts
    alike, and is deterministically sorted (alphabetically) after the pinned
    :data:`_SELF` head.
    """
    from_distributions = {
        raw
        for dist in metadata.distributions()
        if (raw := (dist.metadata["Name"] or "").strip().lower().replace("-", "_")).startswith("fabricatio_")
    }
    from_path = {m.name for m in pkgutil.iter_modules() if m.ispkg and m.name.startswith("fabricatio_")}
    found = from_distributions | from_path
    return ([_SELF] if _SELF in found else []) + sorted(found - {_SELF})
