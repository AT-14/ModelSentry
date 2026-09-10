import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Callable


EXPECTED_SEEDS = [314, 2718, 1618]
EXPECTED_REVISION = "92a244ee98faa8b1dddf0770849ad4961f7fd79c"
BASELINE_V1_FINAL_FIDELITY = 0.7198


def directory_reader(root: Path) -> tuple[dict, Callable[[str], bytes], set[str]]:
    manifest = json.loads((root / "manifest_v2.json").read_text(encoding="utf-8"))
    names = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    return manifest, lambda name: (root / name).read_bytes(), names


def archive_reader(path: Path) -> tuple[dict, Callable[[str], bytes], set[str]]:
    archive = zipfile.ZipFile(path)
    names = {name for name in archive.namelist() if not name.endswith("/")}
    manifest = json.loads(archive.read("manifest_v2.json"))
    return manifest, archive.read, names


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify ModelSentry V2.4 holdout evidence and report its gate status"
    )
    parser.add_argument("evidence", type=Path)
    parser.add_argument(
        "--require-original-gate",
        action="store_true",
        help="Exit unsuccessfully unless the original 12/12 replacement gate passes",
    )
    args = parser.parse_args()

    if args.evidence.is_dir():
        manifest, read_bytes, names = directory_reader(args.evidence)
    elif zipfile.is_zipfile(args.evidence):
        manifest, read_bytes, names = archive_reader(args.evidence)
    else:
        raise SystemExit(f"Evidence path is not a V2 directory or ZIP: {args.evidence}")

    expected_files = manifest.get("files", {})
    missing = sorted(set(expected_files) - names)
    mismatched = sorted(
        name
        for name, expected_hash in expected_files.items()
        if name in names
        and hashlib.sha256(read_bytes(name)).hexdigest() != expected_hash
    )
    protocol_ok = (
        manifest.get("schema_version") == 2
        and manifest.get("profile") == "full"
        and manifest.get("seeds") == EXPECTED_SEEDS
        and manifest.get("source_revision") == EXPECTED_REVISION
        and manifest.get("source_dirty") is False
    )
    if missing or mismatched or not protocol_ok:
        print(f"Protocol metadata valid: {protocol_ok}")
        print(f"Missing files: {missing}")
        print(f"Hash mismatches: {mismatched}")
        raise SystemExit(1)

    summary = json.loads(read_bytes("validation_summary_v2.json"))
    enhanced = summary["mode_overview"]["enhanced"]
    detection_ok = (
        enhanced["attack_runs_detected"] == 12
        and enhanced["attack_runs_tested"] == 12
    )
    benign_ok = (
        enhanced["benign_sessions_mitigated"] == 0
        and enhanced["benign_sessions_tested"] == 90
    )
    fidelity = enhanced["final_fidelity"]["mean"]
    fidelity_ok = fidelity <= BASELINE_V1_FINAL_FIDELITY

    print(f"Manifest files verified: {len(expected_files)}/{len(expected_files)}")
    print(f"Source revision: {manifest['source_revision']}")
    print(
        "Enhanced attack detection: "
        f"{enhanced['attack_runs_detected']}/{enhanced['attack_runs_tested']}"
    )
    print(
        "Enhanced benign mitigation: "
        f"{enhanced['benign_sessions_mitigated']}/{enhanced['benign_sessions_tested']}"
    )
    print(f"Enhanced mean final fidelity: {fidelity:.2%}")
    gate_status = "PASS" if detection_ok and benign_ok and fidelity_ok else "NOT MET"
    print(f"Original 12/12 replacement gate: {gate_status}")

    if args.require_original_gate and not (detection_ok and benign_ok and fidelity_ok):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
