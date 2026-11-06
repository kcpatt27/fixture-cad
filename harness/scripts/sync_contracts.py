"""Copy the canonical contracts into the harness package for builds.

The canonical tool/schema JSON lives in ``docs/``. Hatch cannot include files
outside the project root in an sdist, so build a package-local copy before
``uv build``. The generated directory is gitignored; edit ``docs/tools`` and
``docs/schemas``, never the copy.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "harness" / "src" / "fixture_cad" / "data"


def main() -> int:
    for name in ("tools", "schemas"):
        src = ROOT / "docs" / name
        out = DEST / name
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(src, out)
        print(f"copied {src.relative_to(ROOT)} -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
