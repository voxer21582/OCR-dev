"""Verify the complete release payload using the project verifier."""
from pathlib import Path
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application" / "src"))
from alfa_document_intelligence.runtime_manifest import verify_installation

if __name__ == "__main__":
    if len(sys.argv) != 3 or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", sys.argv[2]):
        raise SystemExit("Expected payload directory and version")
    root = Path(sys.argv[1])
    expected_version = sys.argv[2]
    result = verify_installation(root, root / "runtime-manifest.json")
    if not result.ok:
        print("\n".join(result.problems), file=sys.stderr)
        raise SystemExit(1)
    manifest = json.loads((root / "runtime-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != expected_version:
        raise SystemExit("Payload version does not match installer version")
    print("Payload integrity and version verified")
