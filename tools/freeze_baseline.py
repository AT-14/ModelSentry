import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
EVIDENCE = ROOT / "artifacts" / "validation_corrected"
EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", "artifacts", "data", "submission"}
SOURCE_SUFFIXES = {".py", ".md", ".txt", ".toml", ".ipynb"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if not (EVIDENCE / "manifest.json").exists():
        raise FileNotFoundError("Corrected validation evidence is missing")
    SUBMISSION.mkdir(parents=True, exist_ok=True)

    source_files = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SOURCE_SUFFIXES
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
    )
    evidence_files = sorted(path for path in EVIDENCE.rglob("*") if path.is_file())

    manifest = {
        "version": "Baseline V1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_root": "artifacts/validation_corrected",
        "protocol": {
            "dataset": "Fashion-MNIST",
            "seeds": [42, 7, 123],
            "victim_train_images": 40_000,
            "epochs": 8,
            "monitor_window": 50,
            "monitor_warmup": 50,
            "maximum_query_budget": 5_000,
        },
        "source_files": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in source_files
        },
        "evidence_files": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in evidence_files
        },
    }
    destination = SUBMISSION / "baseline_v1_manifest.json"
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {destination}")
    print(f"Frozen source files: {len(source_files)}")
    print(f"Frozen evidence files: {len(evidence_files)}")


if __name__ == "__main__":
    main()
