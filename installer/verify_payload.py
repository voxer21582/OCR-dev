"""Verify the complete release payload using the project verifier."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application" / "src"))
from alfa_document_intelligence.runtime_manifest import verify_installation

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Expected one payload directory")
    root = Path(sys.argv[1])
    result = verify_installation(root, root / "runtime-manifest.json")
    if not result.ok:
        print("\n".join(result.problems), file=sys.stderr)
        raise SystemExit(1)
    print("Payload integrity verified")
