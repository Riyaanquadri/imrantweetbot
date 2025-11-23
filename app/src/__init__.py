"""Expose the shared `src` helpers under the `app.src` namespace."""
from pathlib import Path

_pkg_dir = Path(__file__).resolve().parent
_src_dir = _pkg_dir.parent.parent / 'src'

__path__ = [str(_pkg_dir)]
if _src_dir.exists():
    __path__.append(str(_src_dir))
