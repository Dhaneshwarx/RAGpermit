"""Private workspace selection; unset preserves the existing sample workspace."""
import os
from pathlib import Path


def workspace_path(relative):
    selected = os.environ.get('PERMITRAG_WORKSPACE')
    if selected is None:
        return Path(__file__).resolve().parent.parent / relative
    root = Path(selected).expanduser()
    if not selected.strip() or not root.is_absolute():
        raise ValueError('PERMITRAG_WORKSPACE must be an absolute folder path.')
    return root / relative
