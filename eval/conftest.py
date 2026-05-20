"""
Shared pytest configuration for the eval suites.

Adds the eval/ directory to sys.path so that `from src.pricing import ...` and
`from src.bank import ...` work uniformly from any of the four test directories.
"""
import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))
