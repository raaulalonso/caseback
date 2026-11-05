"""Caseback protocol reference implementation."""

from caseback_protocol.constants import MAX_FRAME, MAX_PAYLOAD, CASEBACK_MAGIC, CASEBACK_PROTO_VER
from caseback_protocol.crc16 import crc16_ccitt
from caseback_protocol.errors import ErrorCode, FrameError, MessageError, ProtocolError
from caseback_protocol.framing import Frame, decode_frame

__all__ = [
    "crc16_ccitt",
    "ErrorCode",
    "ProtocolError",
    "FrameError",
    "MessageError",
    "MAX_FRAME",
    "MAX_PAYLOAD",
    "CASEBACK_MAGIC",
    "CASEBACK_PROTO_VER",
    "Frame",
    "decode_frame",
]
