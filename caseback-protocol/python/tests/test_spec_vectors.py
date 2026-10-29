"""The golden files must equal the hand-derived hex written in spec/messages.md."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec" / "messages.md"
GOLDEN = ROOT / "fixtures" / "golden"
LINE = re.compile(r"^([a-z_]+\.bin): ((?:[0-9A-F]{2} ?)+)$", re.MULTILINE)
REQUIRED = {"info_request.bin", "info_response.bin", "error.bin", "time_anchor_request.bin", "time_anchor_reply.bin"}


def spec_vectors():
    return {name: bytes.fromhex(hexstr) for name, hexstr in LINE.findall(SPEC.read_text())}


def test_spec_lists_the_required_vectors():
    assert REQUIRED <= set(spec_vectors())


def test_golden_files_equal_spec_hex():
    vectors = spec_vectors()
    assert vectors
    for name, expected in vectors.items():
        assert (GOLDEN / name).read_bytes() == expected, name
