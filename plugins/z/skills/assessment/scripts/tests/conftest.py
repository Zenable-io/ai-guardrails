"""Shared loader for the assessment scripts under test.

The scripts are standalone PEP-723 tools invoked with `uv run --script`, not an
installed package, so there is no import path to resolve them by name. Load each
one by file location instead of putting its directory on sys.path — mutating the
import path leaks into every other test in the session and silently shadows any
same-named module.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def load_script(name: str) -> ModuleType:
    """Import `<name>.py` from the scripts directory as module `name`."""
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
