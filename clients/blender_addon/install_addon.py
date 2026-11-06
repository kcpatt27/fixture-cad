"""Install and enable the Fixture addon in the current Blender profile."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import addon_utils
import bpy

SOURCE = Path(__file__).resolve().parent / "fixture_blender"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fixture-blender-") as temp_dir:
        archive = Path(temp_dir) / "fixture_blender.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for source_file in SOURCE.rglob("*"):
                if source_file.is_file() and "__pycache__" not in source_file.parts:
                    relative = source_file.relative_to(SOURCE.parent)
                    bundle.write(source_file, relative.as_posix())

        result = bpy.ops.preferences.addon_install(
            filepath=str(archive),
            overwrite=True,
            enable_on_install=True,
        )
        if result != {"FINISHED"}:
            raise RuntimeError(f"Fixture addon install failed: {result}")

    bpy.ops.wm.save_userpref()
    loaded, enabled = addon_utils.check("fixture_blender")
    if not loaded or not enabled:
        raise RuntimeError(f"Fixture addon is not enabled: loaded={loaded}, enabled={enabled}")
    print("Fixture addon installed and enabled", flush=True)


if __name__ == "__main__":
    main()
