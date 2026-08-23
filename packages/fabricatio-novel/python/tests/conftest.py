"""Make sibling helper modules (e.g. ``_support``) importable under any pytest import mode.

``--import-mode=importlib`` does not put the tests directory on ``sys.path``,
so bare imports of local helpers would fail without this.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
