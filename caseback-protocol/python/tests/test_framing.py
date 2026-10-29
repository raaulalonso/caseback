import pytest

from caseback_protocol.constants import MAX_FRAME, MAX_PAYLOAD
from caseback_protocol.crc16 import crc16_ccitt
from caseback_protocol.errors import ErrorCode
from caseback_protocol.framing import (
    CASEBACK_MAGIC,
    CASEBACK_PROTO_VER,
    Frame,
    FrameError,
    decode_frame,
)


def frame_bytes(proto_ver=1, msg_type=0x7F, declared=None, payload=b"", magic=CASEBACK_MAGIC):
    n = len(payload) if declared is None else declared
    body = bytes([magic, proto_ver, msg_type]) + n.to_bytes(2, "little") + payload
    return body + crc16_ccitt(body).to_bytes(2, "little")


def code_of(data: bytes) -> ErrorCode:
    with pytest.raises(FrameError) as exc:
        decode_frame(data)
    return exc.value.code


def test_limits():
    assert MAX_PAYLOAD == 175
    assert MAX_FRAME == 182 == 185 - 3 == 5 + MAX_PAYLOAD + 2


def test_encode_layout():
    raw = Frame(msg_type=0x02, payload=b"\x01\x02").encode()
    assert raw[0] == CASEBACK_MAGIC
    assert raw[1] == CASEBACK_PROTO_VER
    assert raw[2] == 0x02
    assert raw[3:5] == (2).to_bytes(2, "little")
    assert raw[5:7] == b"\x01\x02"
    assert len(raw) == 5 + 2 + 2


def test_roundtrip_empty_payload():
    decoded = decode_frame(Frame(msg_type=0x01, payload=b"").encode())
    assert (decoded.msg_type, decoded.payload, decoded.proto_ver) == (0x01, b"", CASEBACK_PROTO_VER)


def test_roundtrip_with_payload():
    payload = bytes(range(32))
    decoded = decode_frame(Frame(msg_type=0x10, payload=payload).encode())
    assert decoded.msg_type == 0x10
    assert decoded.payload == payload


def test_max_payload_roundtrip():
    payload = bytes(range(256))[:MAX_PAYLOAD]
    raw = Frame(msg_type=0x7F, payload=payload).encode()
    assert len(raw) == MAX_FRAME
    assert decode_frame(raw).payload == payload


def test_oversize_payload_rejected_on_decode_and_encode():
    raw = frame_bytes(payload=bytes(MAX_PAYLOAD + 1))
    assert code_of(raw) == ErrorCode.PAYLOAD_TOO_LONG
    with pytest.raises(FrameError) as exc:
        Frame(msg_type=0x01, payload=bytes(MAX_PAYLOAD + 1)).encode()
    assert exc.value.code == ErrorCode.PAYLOAD_TOO_LONG


def test_old_v01_maximum_is_rejected():
    assert code_of(frame_bytes(payload=bytes(512))) == ErrorCode.PAYLOAD_TOO_LONG


def test_bad_magic():
    raw = bytearray(Frame(msg_type=0x01, payload=b"").encode())
    raw[0] = 0x00
    assert code_of(bytes(raw)) == ErrorCode.BAD_MAGIC


def test_bad_crc():
    raw = bytearray(Frame(msg_type=0x01, payload=b"").encode())
    raw[-1] ^= 0xFF
    assert code_of(bytes(raw)) == ErrorCode.BAD_CRC


@pytest.mark.parametrize("ver", [0x00, 0x02, 0xFF])
def test_unsupported_version(ver):
    assert code_of(frame_bytes(proto_ver=ver)) == ErrorCode.UNSUPPORTED_VERSION


def test_truncated_variants():
    raw = Frame(msg_type=0x01, payload=b"\xAA").encode()
    assert code_of(b"") == ErrorCode.TRUNCATED
    assert code_of(raw[:1]) == ErrorCode.TRUNCATED
    assert code_of(raw[:4]) == ErrorCode.TRUNCATED
    assert code_of(raw[:-1]) == ErrorCode.TRUNCATED
    # header declares 8 bytes, only 3 present
    assert code_of(frame_bytes(declared=8, payload=b"\x01\x02\x03")) == ErrorCode.TRUNCATED


def test_length_mismatch_trailing_bytes():
    raw = Frame(msg_type=0x01, payload=b"\x00\x00").encode()
    assert code_of(raw + b"\x00") == ErrorCode.LENGTH_MISMATCH
    assert code_of(frame_bytes(declared=3, payload=b"\x11\x22\x33\x44\x55")) == ErrorCode.LENGTH_MISMATCH


def test_decode_error_order():
    # bad magic wins over version, version over oversize, oversize over truncated
    assert code_of(bytes([0x5A, 0x02, 0x01, 0x00, 0x00, 0, 0])) == ErrorCode.BAD_MAGIC
    assert code_of(bytes([0xA5, 0x02, 0x7F, 0xF4, 0x01])) == ErrorCode.UNSUPPORTED_VERSION
    assert code_of(bytes([0xA5, 0x01, 0x7F, 0xB0, 0x00, 0, 0])) == ErrorCode.PAYLOAD_TOO_LONG
    # length mismatch wins over CRC
    assert code_of(frame_bytes()[:-2] + b"\x00\x00\x00\x00") == ErrorCode.LENGTH_MISMATCH


def test_decode_accepts_unassigned_msg_type():
    assert decode_frame(frame_bytes(msg_type=0xFE)).msg_type == 0xFE


def test_encode_rejects_out_of_range_fields():
    for frame in (Frame(msg_type=0x100, payload=b""), Frame(msg_type=1, payload=b"", proto_ver=256)):
        with pytest.raises(FrameError) as exc:
            frame.encode()
        assert exc.value.code == ErrorCode.INVALID_FIELD


def test_decode_accepts_bytearray_and_memoryview():
    raw = Frame(msg_type=0x01, payload=b"").encode()
    assert decode_frame(bytearray(raw)).msg_type == 1
    assert decode_frame(memoryview(raw)).msg_type == 1
