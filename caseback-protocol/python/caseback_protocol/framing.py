"""Caseback wire framing.

Layout (little-endian):

    offset 0     u8   magic = 0xA5
    offset 1     u8   proto_ver
    offset 2     u8   msg_type
    offset 3..4  u16  payload_len (<= MAX_PAYLOAD)
    offset 5..   u8   payload[payload_len]
    last 2       u16  crc16_ccitt over bytes [0 .. len-2)

Decode order: magic, version, oversize, truncated, length mismatch, CRC.
"""

from __future__ import annotations

from dataclasses import dataclass

from caseback_protocol.constants import (
    CRC_LEN,
    HEADER_LEN,
    MAX_FRAME,
    MAX_PAYLOAD,
    CASEBACK_MAGIC,
    CASEBACK_PROTO_VER,
)
from caseback_protocol.crc16 import crc16_ccitt
from caseback_protocol.errors import ErrorCode, FrameError

__all__ = [
    "CRC_LEN",
    "HEADER_LEN",
    "MAX_FRAME",
    "MAX_PAYLOAD",
    "CASEBACK_MAGIC",
    "CASEBACK_PROTO_VER",
    "Frame",
    "FrameError",
    "decode_frame",
]


@dataclass(frozen=True)
class Frame:
    msg_type: int
    payload: bytes
    proto_ver: int = CASEBACK_PROTO_VER

    def encode(self) -> bytes:
        if not 0 <= self.msg_type <= 0xFF:
            raise FrameError(ErrorCode.INVALID_FIELD, f"msg_type out of range: {self.msg_type}")
        if not 0 <= self.proto_ver <= 0xFF:
            raise FrameError(ErrorCode.INVALID_FIELD, f"proto_ver out of range: {self.proto_ver}")
        if len(self.payload) > MAX_PAYLOAD:
            raise FrameError(ErrorCode.PAYLOAD_TOO_LONG, f"payload too long: {len(self.payload)}")
        body = (
            bytes([CASEBACK_MAGIC, self.proto_ver, self.msg_type])
            + len(self.payload).to_bytes(2, "little")
            + bytes(self.payload)
        )
        return body + crc16_ccitt(body).to_bytes(2, "little")


def decode_frame(data: bytes) -> Frame:
    data = bytes(data)
    if len(data) < 1:
        raise FrameError(ErrorCode.TRUNCATED, "frame truncated")
    if data[0] != CASEBACK_MAGIC:
        raise FrameError(ErrorCode.BAD_MAGIC, f"bad magic: 0x{data[0]:02X}")
    if len(data) < 2:
        raise FrameError(ErrorCode.TRUNCATED, "frame truncated")
    if data[1] != CASEBACK_PROTO_VER:
        raise FrameError(ErrorCode.UNSUPPORTED_VERSION, f"unsupported proto_ver: {data[1]}")
    if len(data) < HEADER_LEN:
        raise FrameError(ErrorCode.TRUNCATED, "frame truncated")
    payload_len = int.from_bytes(data[3:5], "little")
    if payload_len > MAX_PAYLOAD:
        raise FrameError(ErrorCode.PAYLOAD_TOO_LONG, f"payload too long: {payload_len}")
    expected = HEADER_LEN + payload_len + CRC_LEN
    if len(data) < expected:
        raise FrameError(ErrorCode.TRUNCATED, f"frame truncated: got {len(data)}, want {expected}")
    if len(data) > expected:
        raise FrameError(
            ErrorCode.LENGTH_MISMATCH, f"length mismatch: got {len(data)}, want {expected}"
        )
    crc_wire = int.from_bytes(data[-CRC_LEN:], "little")
    crc_calc = crc16_ccitt(data[:-CRC_LEN])
    if crc_wire != crc_calc:
        raise FrameError(
            ErrorCode.BAD_CRC, f"crc mismatch: wire=0x{crc_wire:04X} calc=0x{crc_calc:04X}"
        )
    return Frame(
        msg_type=data[2],
        payload=data[HEADER_LEN : HEADER_LEN + payload_len],
        proto_ver=data[1],
    )
