"""Verify the complete release payload using the project verifier."""
from pathlib import Path
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application" / "src"))
from alfa_document_intelligence.runtime_manifest import verify_installation

_COMPONENT_TYPES = frozenset({"application", "framework", "library", "container", "platform",
                              "operating-system", "device", "device-driver", "firmware", "file",
                              "machine-learning-model", "data"})

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
    required = {"sbom.json", "THIRD_PARTY_NOTICES.txt"}
    if not required <= set(manifest.get("files", {})):
        raise SystemExit("Payload must include inventory and notices in its manifest")
    if any(manifest["files"][name]["size"] == 0 for name in required):
        raise SystemExit("Payload inventory and notices must not be empty")
    try:
        sbom = json.loads((root / "sbom.json").read_text(encoding="utf-8"))
        notices = (root / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        raise SystemExit("Payload inventory or notices are unreadable or invalid")
    if (not isinstance(sbom, dict) or sbom.get("bomFormat") != "CycloneDX"
            or sbom.get("specVersion") != "1.5" or not isinstance(sbom.get("components"), list)
            or not sbom["components"] or type(sbom.get("version")) is not int or sbom["version"] < 1
            or any(not isinstance(c, dict) or not isinstance(c.get("type"), str) or c["type"] not in _COMPONENT_TYPES
                   or not isinstance(c.get("name"), str) or not c["name"].strip() for c in sbom["components"])):
        raise SystemExit("Payload inventory has invalid basic CycloneDX 1.5 fields")
    if not notices.strip():
        raise SystemExit("Payload notices must not be blank")
    print("Payload integrity and version verified")
