"""Regenerate golden fixtures. Run from caseback-protocol/python after installing the package.

Writes caseback-protocol/fixtures/golden and, when present, the copy used by the Swift tests.
"""

from pathlib import Path

from caseback_protocol import golden

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "fixtures" / "golden"
SWIFT_OUT = ROOT.parent / "apps" / "ios" / "CasebackProtocol" / "Tests" / "CasebackProtocolTests" / "Fixtures" / "golden"


def write_all(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.bin"):
        stale.unlink()
    for name, data in golden.positive_frames().items():
        (out / f"{name}.bin").write_bytes(data)
    for name, (data, _) in golden.negative_frames().items():
        (out / f"{name}.bin").write_bytes(data)
    (out / "manifest.txt").write_text(golden.manifest())


def main() -> None:
    write_all(OUT)
    print(f"wrote fixtures to {OUT}")
    if SWIFT_OUT.parent.exists():
        write_all(SWIFT_OUT)
        print(f"wrote fixtures to {SWIFT_OUT}")


if __name__ == "__main__":
    main()
