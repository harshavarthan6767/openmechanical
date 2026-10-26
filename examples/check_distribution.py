"""Check local release artifacts without importing the engineering runtime."""

from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from pathlib import Path


def main():
    root = Path(__file__).parents[1]
    wheel = root / "dist/openmechanical-0.1.0-py3-none-any.whl"
    source = root / "dist/openmechanical-0.1.0.tar.gz"
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        required = {f"openmechanical/{p.name}" for p in (root / "src/openmechanical").glob("*.py")}
        if not required.issubset(names):
            raise RuntimeError(f"wheel modules missing: {required - set(names)}")
        if not any(name.endswith("licenses/LICENSE") for name in names):
            raise RuntimeError("wheel license is missing")
    with tarfile.open(source) as archive:
        source_names = archive.getnames()
        for name in source_names:
            parts = Path(name).parts[1:]
            if parts and parts[0] in ("runs", "dist", ".venv", ".pytest_cache", ".ruff_cache"):
                raise RuntimeError(f"generated content leaked into source archive: {name}")
    result = {
        "status": "passed",
        "wheel_modules": sorted(required),
        "wheel_license_present": True,
        "generated_content_excluded": True,
        "artifacts": {
            p.name: {
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes": p.stat().st_size,
            }
            for p in (wheel, source)
        },
    }
    (root / "dist/build-verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
