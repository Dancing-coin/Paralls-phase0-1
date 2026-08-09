from __future__ import annotations

import sys
from pathlib import Path


backend_root = Path(__file__).resolve().parents[3] / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))
