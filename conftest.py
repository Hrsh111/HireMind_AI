"""Make root and backend modules importable from the test suite."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
for _p in (ROOT, ROOT / "backend"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)
