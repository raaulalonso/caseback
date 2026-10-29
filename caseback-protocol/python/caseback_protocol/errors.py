"""Error taxonomy shared by framing, message decoding and the ERROR message (spec/messages.md)."""

from __future__ import annotations

from enum import IntEnum


class ErrorCode(IntEnum):
    NONE = 0x0000
    TRUNCATED = 0x0001
    BAD_MAGIC = 0x0002
    UNSUPPORTED_VERSION = 0x0003
    PAYLOAD_TOO_LONG = 0x0004
    LENGTH_MISMATCH = 0x0005
    BAD_CRC = 0x0006
    UNKNOWN_MSG_TYPE = 0x0100
    BAD_PAYLOAD_LENGTH = 0x0101
    INVALID_FIELD = 0x0102
    UNSUPPORTED = 0x0103
    WRONG_DIRECTION = 0x0104
    LINK_NOT_ENCRYPTED = 0x0200
    BUSY = 0x0201
    BAD_STATE = 0x0202
    NO_SUCH_STREAM = 0x0203
    CURSOR_OUT_OF_RANGE = 0x0204
    INTERNAL = 0x0300
    # local only, never sent on the wire
    BUFFER_TOO_SMALL = 0xF001
    NULL_ARGUMENT = 0xF002


class ProtocolError(ValueError):
    """Base error carrying an ErrorCode and, for INVALID_FIELD, the payload offset in `detail`."""

    def __init__(self, code: ErrorCode, message: str, detail: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail


class FrameError(ProtocolError):
    """Raised when a frame cannot be encoded or decoded."""


class MessageError(ProtocolError):
    """Raised when a payload does not match its message layout."""
