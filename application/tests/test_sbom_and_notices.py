"""SBOM and third-party notices (M6 Task 7, REQ-107) on synthetic dist-info trees; no network."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import pytest

_REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPOSITORY / "installer"))

import _distinfo  # noqa: E402
import build_payload  # noqa: E402
import notices  # noqa: E402
import sbom  # noqa: E402
from alfa_document_intelligence.rapidocr_runtime_factory import MODEL_ARTIFACTS  # noqa: E402

LOCK = _REPOSITORY / "requirements" / "ocr2-runtime-cp313-win-amd64.lock"
PINS = _REPOSITORY / "installer" / "pins.json"


def _locked() -> list[tuple[str, str, str]]:
    """Independent reading of the real lock: (name, version, sha256)."""
    text = LOCK.read_text(encoding="utf-8")
    found = re.findall(r"^([A-Za-z0-9._-]+)==(\S+) \\\n\s+--hash=sha256:([0-9a-f]{64})", text, re.MULTILINE)
    assert len(found) == 22
    return found


def _dist_info(site: Path, name: str, version: str, metadata_extra: str, files: dict[str, str]) -> Path:
    folder = site / f"{name.replace('-', '_')}-{version}.dist-info"
    folder.mkdir(parents=True)
    (folder / "METADATA").write_text(
        f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n{metadata_extra}", encoding="utf-8"
    )
    for relative, text in files.items():
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return folder


@pytest.fixture
def payload(tmp_path) -> Path:
    root = tmp_path / "0.6.0"
    site = root / "python" / "Lib" / "site-packages"
    (root / "python").mkdir(parents=True)
    (root / "python" / "LICENSE.txt").write_text("PSF LICENSE TEXT\r\n", encoding="utf-8", newline="")
    for name, version, _digest in _locked():
        files = {"licenses/LICENSE": f"Licence text of {name}\n"}
        if name == "rapidocr":
            files["licenses/MODEL_LICENSES.md"] = "MODEL LICENCE TEXT\n"
        _dist_info(site, name, version, "License-Expression: MIT\nLicense-File: LICENSE\n", files)
    return root


def test_every_locked_package_is_in_sbom(payload):
    document = sbom.build_sbom(payload, LOCK, PINS)
    by_purl = {c["purl"]: c for c in document["components"] if c.get("purl", "").startswith("pkg:pypi/")}
    assert len(by_purl) == 22
    for name, version, digest in _locked():
        component = by_purl[f"pkg:pypi/{name.lower()}@{version}"]
        assert component["version"] == version
        assert component["hashes"] == [{"alg": "SHA-256", "content": digest}]
        assert component["licenses"] == [{"expression": "MIT"}]


def test_sbom_describes_python_models_ocr2_and_nsis(payload):
    document = sbom.build_sbom(payload, LOCK, PINS)
    assert document["bomFormat"] == "CycloneDX" and document["specVersion"] == "1.5"
    by_name = {c["name"]: c for c in document["components"]}
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    assert by_name["cpython"]["hashes"][0]["content"] == pins["embeddable"]["sha256"]
    assert by_name["cpython"]["version"] == pins["embeddable"]["version"]
    for filename, digest in MODEL_ARTIFACTS:
        model = by_name[filename.removesuffix(".onnx")]
        assert model["hashes"] == [{"alg": "SHA-256", "content": digest}]
    assert by_name["ocr2"]["version"] == "0.6.0" and by_name["ocr2"]["licenses"] == [{"license": {"id": "MIT"}}]
    assert by_name["nsis"]["scope"] == "excluded"
    assert [c["name"] for c in document["components"] if c["scope"] == "excluded"] == ["nsis"]
    assert len(document["components"]) == 22 + 1 + 2 + 1 + 1


def test_sbom_has_no_ffmpeg_component(payload):
    text = sbom.dump_sbom(sbom.build_sbom(payload, LOCK, PINS)).lower()
    assert "ffmpeg" not in text


def test_sbom_is_deterministic(payload, tmp_path):
    first = sbom.dump_sbom(sbom.build_sbom(payload, LOCK, PINS))
    second = sbom.dump_sbom(sbom.build_sbom(payload, LOCK, PINS))
    assert first == second and first.endswith("}\n")
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    sbom.write_sbom(sbom.build_sbom(payload, LOCK, PINS), a)
    sbom.write_sbom(sbom.build_sbom(payload, LOCK, PINS), b)
    assert a.read_bytes() == b.read_bytes()
    assert re.fullmatch(r"urn:uuid:[0-9a-f-]{36}", json.loads(first)["serialNumber"])


def test_sbom_refuses_a_locked_package_missing_from_the_payload(payload):
    victim = next(payload.glob("python/Lib/site-packages/idna-*"))
    (victim / "METADATA").unlink()
    with pytest.raises(sbom.SbomError, match="idna"):
        sbom.build_sbom(payload, LOCK, PINS)


def test_licence_metadata_fallbacks(tmp_path):
    root = tmp_path / "1.0.0"
    site = root / "python" / "Lib" / "site-packages"
    _dist_info(site, "a", "1", "License: Apache 2.0\n  second line\nClassifier: License :: OSI Approved :: MIT License\n", {})
    _dist_info(site, "b", "1", "Classifier: License :: OSI Approved\nClassifier: License :: OSI Approved :: BSD License\n", {})
    _dist_info(site, "c", "1", "", {})
    _dist_info(site, "d", "1", "License-Expression: Apache-2.0 OR MIT\nLicense: ignored\n", {})
    found = {info.name: (info.licence, info.licence_is_expression) for info in _distinfo.read_all(root)}
    assert found == {
        "a": ("Apache 2.0", False), "b": ("BSD License", False),
        "c": ("NOASSERTION", False), "d": ("Apache-2.0 OR MIT", True),
    }


def test_licence_files_include_declared_and_conventional_names(tmp_path):
    root = tmp_path / "1.0.0"
    folder = _dist_info(
        root / "python" / "Lib" / "site-packages", "pkg", "1", "License-File: sub/EXTRA.txt\n",
        {"licenses/sub/EXTRA.txt": "x", "COPYING": "y", "NOTICE.md": "z", "RECORD": "no", "licenses/LICENSE": "w"},
    )
    names = [f.relative_to(folder).as_posix() for f in _distinfo.read_dist_info(folder).licence_files]
    assert names == ["COPYING", "NOTICE.md", "licenses/LICENSE", "licenses/sub/EXTRA.txt"]


def test_notices_contain_every_licence_text(payload):
    text = notices.build_notices(payload)
    assert "PSF LICENSE TEXT" in text and "\r" not in text
    assert "MODEL LICENCE TEXT" in text and "--- licenses/MODEL_LICENSES.md ---" in text
    for name, version, _digest in _locked():
        assert f"Licence text of {name}\n" in text
        assert f"{name} {version}" in text


def test_every_dist_info_has_licence_text_in_notices(payload):
    for victim in ("six", "idna"):
        for path in next(payload.glob(f"python/Lib/site-packages/{victim}-*")).rglob("LICENSE"):
            path.unlink()
    with pytest.raises(_distinfo.LicenceTextMissingError) as raised:
        notices.build_notices(payload)
    assert raised.value.packages == ["idna 3.20", "six 1.17.0"]
    assert "idna" in str(raised.value) and "six" in str(raised.value)


def test_notices_need_python_licence_and_model_licences(payload):
    (payload / "python" / "LICENSE.txt").unlink()
    next(payload.glob("python/Lib/site-packages/rapidocr-*/licenses/MODEL_LICENSES.md")).unlink()
    with pytest.raises(_distinfo.LicenceTextMissingError) as raised:
        notices.build_notices(payload)
    assert raised.value.packages == ["cpython (python/LICENSE.txt)", "rapidocr (MODEL_LICENSES.md)"]


def test_missing_licence_text_stops_the_build_with_exit_code_3(monkeypatch, capsys):
    def refuse(**_kwargs):
        raise _distinfo.LicenceTextMissingError(["flatbuffers 25.12.19", "onnxruntime 1.31.1"])

    monkeypatch.setattr(build_payload, "run", refuse)
    assert build_payload.main(["--version", "0.6.0"]) == 3
    error = capsys.readouterr().err
    assert "flatbuffers 25.12.19" in error and "onnxruntime 1.31.1" in error
