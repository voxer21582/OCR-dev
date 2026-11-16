"""Shared ``*.dist-info`` reading for the SBOM and the notices (M6 Task 7)."""
from __future__ import annotations

import email
from dataclasses import dataclass
from pathlib import Path
import re

NOASSERTION = "NOASSERTION"
SITE_PACKAGES = ("python", "Lib", "site-packages")
_LICENCE_PREFIXES = ("license", "licence", "copying", "notice", "authors")
_PACKAGE_DIR_PREFIXES = ("license", "licence", "copying", "notice", "thirdpartynotices")
INSTALLER_DIR = Path(__file__).resolve().parent
# R26: explicit licence text for one exact (normalised name, version) whose wheel ships none.
LICENCE_OVERRIDES: dict[tuple[str, str], Path] = {
    ("flatbuffers", "25.12.19"): INSTALLER_DIR / "licenses" / "flatbuffers-25.12.19.txt",
}


class LicenceTextMissingError(RuntimeError):
    """Some packages ship no licence text file; ``packages`` lists them."""

    def __init__(self, packages: list[str]):
        self.packages = packages
        super().__init__("pacchetti senza file di licenza: " + ", ".join(packages))


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass(frozen=True)
class DistInfo:
    path: Path
    name: str
    version: str
    licence: str
    licence_is_expression: bool
    licence_files: tuple[Path, ...]
    override_source: str = ""

    def display(self, file: Path) -> str:
        """Name of ``file`` relative to the dist-info, or to site-packages for package-folder files."""
        for base in (self.path, self.path.parent, INSTALLER_DIR.parent):
            try:
                return file.relative_to(base).as_posix()
            except ValueError:
                continue
        return file.name

    @property
    def label(self) -> str:
        return f"{self.name} {self.version}"


def site_packages(payload_root: Path) -> Path:
    return Path(payload_root).joinpath(*SITE_PACKAGES)


def _licence(message) -> tuple[str, bool]:
    expression = (message.get("License-Expression") or "").strip()
    if expression:
        return expression, True
    free = (message.get("License") or "").strip().splitlines()
    if free and free[0].strip():
        return free[0].strip(), False
    for classifier in message.get_all("Classifier") or []:
        parts = [part.strip() for part in classifier.split("::")]
        if parts[0] == "License" and len(parts) > 1 and parts[-1] != "OSI Approved":
            return parts[-1], False
    return NOASSERTION, False


def _licence_files(path: Path, declared: list[str]) -> tuple[Path, ...]:
    found: dict[Path, None] = {}
    root = path.resolve()

    def add(candidate: Path) -> None:
        resolved = candidate.resolve()
        if resolved.is_file() and resolved.is_relative_to(root):
            found[candidate] = None

    for entry in declared:
        add(path / "licenses" / entry)
        add(path / entry)
    licences = path / "licenses"
    if licences.is_dir():
        for candidate in sorted(licences.rglob("*")):
            add(candidate)
    for candidate in sorted(path.iterdir()):
        if candidate.name.lower().startswith(_LICENCE_PREFIXES):
            add(candidate)
    return tuple(sorted(found, key=lambda p: p.relative_to(path).as_posix()))


def _package_dir_files(path: Path) -> list[Path]:
    """Licence files the wheel installs in its own top-level folder, found through RECORD (R25)."""
    record = path / "RECORD"
    if not record.is_file():
        return []
    site = path.parent
    found = []
    for line in record.read_text(encoding="utf-8", errors="replace").splitlines():
        entry = line.rsplit(",", 2)[0].replace("\\", "/")
        parts = entry.split("/")
        if len(parts) == 2 and not parts[0].endswith(".dist-info") and parts[1].lower().startswith(_PACKAGE_DIR_PREFIXES):
            candidate = site / parts[0] / parts[1]
            if candidate.is_file() and candidate.resolve().is_relative_to(site.resolve()):
                found.append(candidate)
    return found


def read_dist_info(path: Path, overrides: dict[tuple[str, str], Path] | None = None) -> DistInfo:
    overrides = LICENCE_OVERRIDES if overrides is None else overrides
    message = email.message_from_string((path / "METADATA").read_text(encoding="utf-8", errors="replace"))
    licence, is_expression = _licence(message)
    declared = [value.strip() for value in message.get_all("License-File") or []]
    name = (message.get("Name") or path.name.split("-")[0]).strip()
    version = (message.get("Version") or "").strip()
    files = list(_licence_files(path, declared)) + _package_dir_files(path)
    source = ""
    override = overrides.get((normalise(name), version))
    if override is not None and Path(override).is_file():
        files.append(Path(override))
        try:
            source = Path(override).resolve().relative_to(INSTALLER_DIR.parent).as_posix()
        except ValueError:
            source = Path(override).as_posix()
    return DistInfo(path, name, version, licence, is_expression, tuple(files), source)


def read_all(payload_root: Path, overrides: dict[tuple[str, str], Path] | None = None) -> list[DistInfo]:
    packages = site_packages(payload_root)
    infos = [read_dist_info(p, overrides) for p in sorted(packages.glob("*.dist-info")) if (p / "METADATA").is_file()]
    return sorted(infos, key=lambda info: (normalise(info.name), info.version))
