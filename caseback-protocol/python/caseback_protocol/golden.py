"""Reference values behind the golden fixtures in caseback-protocol/fixtures/golden.

Every field value inside one message is distinct and most bytes are above 0x7F, so swapped fields, sign
extension and wrong endianness show up. The same values are hard-coded in the Swift and C tests, and the
expected bytes of the main messages are written out by hand in spec/messages.md.
"""

from __future__ import annotations

from caseback_protocol.constants import (
    CAP_ENCRYPTED_ONLY,
    CAP_IBI_LOG,
    CAP_PPG_RAW,
    CAP_PPG_SUMMARY,
    MAX_PAYLOAD,
    MSG_CONFIG_STATE,
    CASEBACK_MAGIC,
    CASEBACK_PROTO_VER,
)
from caseback_protocol.crc16 import crc16_ccitt
from caseback_protocol.errors import ErrorCode
from caseback_protocol.framing import Frame
from caseback_protocol.messages import (
    Battery,
    Config,
    ErrorMessage,
    InfoResponse,
    TimeAnchorReply,
    TimeAnchorRequest,
    encode_battery_frame,
    encode_battery_query_frame,
    encode_config_query_frame,
    encode_config_set_frame,
    encode_config_state_frame,
    encode_error_frame,
    encode_info_request,
    encode_info_response_frame,
    encode_time_anchor_reply_frame,
    encode_time_anchor_request_frame,
)

FRAMING_MSG_TYPE = 0x7F  # unassigned type used by framing-only fixtures

INFO = InfoResponse(
    device_id=bytes([0x8B, 0x9C, 0xAD, 0xBE, 0xCF, 0xD0, 0xE1, 0xF2]),
    hw_rev=0x8102,
    fw_rev=0x9304,
    capabilities=CAP_PPG_RAW | CAP_PPG_SUMMARY | CAP_IBI_LOG | CAP_ENCRYPTED_ONLY,
)
ERROR = ErrorMessage(code=ErrorCode.INVALID_FIELD, msg_type=0x20, detail=0x0C)
ERROR_UNKNOWN_CODE = ErrorMessage(code=0x9ABC, msg_type=0xC7, detail=0xE1)
ANCHOR_REQUEST = TimeAnchorRequest(utc_ms=0x0000_01A2_B3C4_D5E6)
ANCHOR_REPLY = TimeAnchorReply(boot_id=0xC0DE_FACE, uptime_ms=0x0000_00E4_D3C2_B1A0)
CONFIG_SET = Config(
    mode=2,
    payload_format=1,
    ppg_rate_hz=(25, 200, 100, 400),
    burst_period_s=300,
    burst_len_s=30,
    led_mask=0b101,
    led_green_ma=42,
    led_red_ma=27,
    led_ir_ma=33,
    wear_ppg_dc=0x0005_B7C9,
    wear_motion_thr=500,
    wear_probe_period_ms=1000,
)
CONFIG_STATE = Config(
    mode=1,
    payload_format=0,
    ppg_rate_hz=(48, 32, 128, 400),
    burst_period_s=600,
    burst_len_s=45,
    led_mask=0b111,
    led_green_ma=60,
    led_red_ma=52,
    led_ir_ma=41,
    wear_ppg_dc=0x0007_FFFF,
    wear_motion_thr=3000,
    wear_probe_period_ms=5000,
)
BATTERY = Battery(voltage_mv=4013, charging=1, percent=87, avg_current_ua=(210, 854, 6699, 15758))

MAX_PAYLOAD_BYTES = bytes((i * 37 + 0x80) & 0xFF for i in range(MAX_PAYLOAD))
A5_PAYLOAD = b"\xA5" * 8 + b"\xA5\x01\x7F\x04\x00" + b"\xA5" * 8


def _raw_frame(proto_ver: int, msg_type: int, declared_len: int, payload: bytes) -> bytes:
    body = bytes([CASEBACK_MAGIC, proto_ver, msg_type]) + declared_len.to_bytes(2, "little") + payload
    return body + crc16_ccitt(body).to_bytes(2, "little")


def positive_frames() -> dict[str, bytes]:
    """name -> valid frame; every one decodes at the frame level."""
    return {
        "info_request": encode_info_request(),
        "info_response": encode_info_response_frame(INFO),
        "error": encode_error_frame(ERROR),
        "error_unknown_code": encode_error_frame(ERROR_UNKNOWN_CODE),
        "time_anchor_request": encode_time_anchor_request_frame(ANCHOR_REQUEST),
        "time_anchor_reply": encode_time_anchor_reply_frame(ANCHOR_REPLY),
        "config_query": encode_config_query_frame(),
        "config_set": encode_config_set_frame(CONFIG_SET),
        "config_state": encode_config_state_frame(CONFIG_STATE),
        "battery_query": encode_battery_query_frame(),
        "battery": encode_battery_frame(BATTERY),
        "max_payload": Frame(FRAMING_MSG_TYPE, MAX_PAYLOAD_BYTES).encode(),
        "a5_payload": Frame(FRAMING_MSG_TYPE, A5_PAYLOAD).encode(),
    }


def negative_frames() -> dict[str, tuple[bytes, ErrorCode]]:
    """name -> (bytes, the one error every decoder must report)."""
    info = encode_info_response_frame(INFO)
    bad_magic = bytes([0x5A]) + info[1:]
    bad_crc = info[:-1] + bytes([info[-1] ^ 0xFF])
    return {
        "neg_bad_magic": (bad_magic, ErrorCode.BAD_MAGIC),
        "neg_bad_crc": (bad_crc, ErrorCode.BAD_CRC),
        "neg_oversize": (
            _raw_frame(CASEBACK_PROTO_VER, FRAMING_MSG_TYPE, MAX_PAYLOAD + 1, bytes(MAX_PAYLOAD + 1)),
            ErrorCode.PAYLOAD_TOO_LONG,
        ),
        "neg_oversize_short": (
            bytes([CASEBACK_MAGIC, CASEBACK_PROTO_VER, FRAMING_MSG_TYPE]) + (MAX_PAYLOAD + 1).to_bytes(2, "little")
            + b"\x00\x00",
            ErrorCode.PAYLOAD_TOO_LONG,
        ),
        "neg_length_mismatch": (
            _raw_frame(CASEBACK_PROTO_VER, FRAMING_MSG_TYPE, 3, b"\x11\x22\x33\x44\x55"),
            ErrorCode.LENGTH_MISMATCH,
        ),
        "neg_trailing_bytes": (info + b"\x00\x00", ErrorCode.LENGTH_MISMATCH),
        "neg_unsupported_version": (
            _raw_frame(0x02, 0x01, 0, b""),
            ErrorCode.UNSUPPORTED_VERSION,
        ),
        "neg_magic_and_version": (
            bytes([0x5A, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00]),
            ErrorCode.BAD_MAGIC,
        ),
        "neg_version_and_oversize": (
            bytes([CASEBACK_MAGIC, 0x02, FRAMING_MSG_TYPE, 0xF4, 0x01]),
            ErrorCode.UNSUPPORTED_VERSION,
        ),
        "neg_truncated": (info[:-1], ErrorCode.TRUNCATED),
        "neg_truncated_declared": (
            _raw_frame(CASEBACK_PROTO_VER, FRAMING_MSG_TYPE, 8, b"\x01\x02\x03"),
            ErrorCode.TRUNCATED,
        ),
        "neg_truncated_header": (info[:3], ErrorCode.TRUNCATED),
        "neg_empty": (b"", ErrorCode.TRUNCATED),
    }


def manifest() -> str:
    lines = [
        "# name.bin ok <msg_type> <payload_len> | name.bin <error>",
        "# error names: truncated bad_magic unsupported_version payload_too_long length_mismatch bad_crc",
        "# generated by python/tools/gen_fixtures.py; do not edit",
    ]
    for name, data in positive_frames().items():
        lines.append(f"{name}.bin ok 0x{data[2]:02x} {int.from_bytes(data[3:5], 'little')}")
    for name, (_, code) in negative_frames().items():
        lines.append(f"{name}.bin {code.name.lower()}")
    return "\n".join(lines) + "\n"
