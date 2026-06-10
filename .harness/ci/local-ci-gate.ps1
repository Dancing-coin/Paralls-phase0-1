$ErrorActionPreference = "Stop"

python -m pytest -q scripts\verification\tests
python -m compileall -q scripts\verification
python scripts\verification\harness.py --profile all
