from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_ROOT.parent

# 顺序有意义：backend 必须在 repo root 之前，这样 `import tools` 命中
# backend 侧的同名模块时不会因 repo 根的 tools/ 抢占而行为变化。
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# 部分测试以仓库根为导入基准：
#   from scripts.verification...   （48 个测试）
#   from backend.tests...          （4 个测试）
#   import tools                   （2 个测试，backend/tools 不存在时才落到仓库根）
# 这两者在仓库根下都没有 __init__.py，作为 PEP 420 命名空间包导入。
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
