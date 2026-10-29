"""Caseback message codecs (proto_ver 0x01, spec v0.2).

Implemented: INFO, ERROR, TIME_ANCHOR, CONFIG_SET/CONFIG_STATE, BATTERY.
STREAM_DATA, STREAM_CONTROL, HISTORY_QUERY and HISTORY_ACK are specified only.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from caseback_protocol.constants import (
    CHARGING_CHARGING,
    CHARGING_COMPLETE,
    CHARGING_FAULT,
    CHARGING_NOT_CHARGING,
    CHARGING_UNKNOWN,
    MAX_PPG_RATE_HZ,
    MODE_RAW,
    MSG_BATTERY,
    MSG_CONFIG_SET,
    MSG_CONFIG_STATE,
    MSG_ERROR,
    MSG_INFO_REQUEST,
    MSG_INFO_RESPONSE,
    MSG_TIME_ANCHOR,
    PAYLOAD_FORMAT_STREAM_RAW,
    PERCENT_UNKNOWN,
)
from caseback_protocol.errors import ErrorCode, MessageError
from caseback_protocol.framing import Frame

DEVICE_ID_LEN = 8
INFO_RESPONSE_PAYLOAD_LEN = 16
ERROR_PAYLOAD_LEN = 4
TIME_ANCHOR_REQUEST_LEN = 8
TIME_ANCHOR_REPLY_LEN = 12
CONFIG_PAYLOAD_LEN = 26
BATTERY_PAYLOAD_LEN = 12

_INFO = struct.Struct("<8sHHI")
_ERROR = struct.Struct("<HBB")
_ANCHOR_REQ = struct.Struct("<Q")
_ANCHOR_REPLY = struct.Struct("<IQ")
_CONFIG = struct.Struct("<BB4HHHB3BIHH")
_BATTERY = struct.Struct("<HBB4H")


def _invalid(field: str, offset: int) -> MessageError:
    return MessageError(ErrorCode.INVALID_FIELD, f"invalid {field}", detail=offset)


def _check_uint(value: int, bits: int, field: str, offset: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < (1 << bits):
        raise _invalid(field, offset)
    return value


def _check_len(payload: bytes, want: int, what: str) -> None:
    if len(payload) != want:
        raise MessageError(
            ErrorCode.BAD_PAYLOAD_LENGTH,
            f"{what} payload must be {want} bytes, got {len(payload)}",
            detail=min(want, 255),
        )


def _check_type(frame: Frame, msg_type: int) -> None:
    if frame.msg_type != msg_type:
        raise MessageError(
            ErrorCode.UNKNOWN_MSG_TYPE, f"expected msg_type 0x{msg_type:02X}, got 0x{frame.msg_type:02X}"
        )


# INFO ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class InfoResponse:
    device_id: bytes
    hw_rev: int
    fw_rev: int
    capabilities: int

    def encode_payload(self) -> bytes:
        if len(self.device_id) != DEVICE_ID_LEN:
            raise _invalid("device_id", 0)
        return _INFO.pack(
            bytes(self.device_id),
            _check_uint(self.hw_rev, 16, "hw_rev", 8),
            _check_uint(self.fw_rev, 16, "fw_rev", 10),
            _check_uint(self.capabilities, 32, "capabilities", 12),
        )


def decode_info_response(payload: bytes) -> InfoResponse:
    payload = bytes(payload)
    _check_len(payload, INFO_RESPONSE_PAYLOAD_LEN, "info response")
    device_id, hw_rev, fw_rev, capabilities = _INFO.unpack(payload)
    return InfoResponse(device_id, hw_rev, fw_rev, capabilities)


def decode_info_response_frame(frame: Frame) -> InfoResponse:
    _check_type(frame, MSG_INFO_RESPONSE)
    return decode_info_response(frame.payload)


def encode_info_request() -> bytes:
    return Frame(msg_type=MSG_INFO_REQUEST, payload=b"").encode()


def encode_info_response_frame(resp: InfoResponse) -> bytes:
    return Frame(msg_type=MSG_INFO_RESPONSE, payload=resp.encode_payload()).encode()


# ERROR -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ErrorMessage:
    code: int  # an ErrorCode value, or any u16 from a newer peer
    msg_type: int
    detail: int = 0

    def encode_payload(self) -> bytes:
        return _ERROR.pack(
            _check_uint(int(self.code), 16, "code", 0),
            _check_uint(self.msg_type, 8, "msg_type", 2),
            _check_uint(self.detail, 8, "detail", 3),
        )


def decode_error(payload: bytes) -> ErrorMessage:
    payload = bytes(payload)
    _check_len(payload, ERROR_PAYLOAD_LEN, "error")
    return ErrorMessage(*_ERROR.unpack(payload))


def decode_error_frame(frame: Frame) -> ErrorMessage:
    _check_type(frame, MSG_ERROR)
    return decode_error(frame.payload)


def encode_error_frame(msg: ErrorMessage) -> bytes:
    return Frame(msg_type=MSG_ERROR, payload=msg.encode_payload()).encode()


# TIME_ANCHOR -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeAnchorRequest:
    utc_ms: int

    def encode_payload(self) -> bytes:
        return _ANCHOR_REQ.pack(_check_uint(self.utc_ms, 64, "utc_ms", 0))


@dataclass(frozen=True)
class TimeAnchorReply:
    boot_id: int
    uptime_ms: int

    def encode_payload(self) -> bytes:
        return _ANCHOR_REPLY.pack(
            _check_uint(self.boot_id, 32, "boot_id", 0),
            _check_uint(self.uptime_ms, 64, "uptime_ms", 4),
        )


def decode_time_anchor_request(payload: bytes) -> TimeAnchorRequest:
    payload = bytes(payload)
    _check_len(payload, TIME_ANCHOR_REQUEST_LEN, "time anchor request")
    return TimeAnchorRequest(*_ANCHOR_REQ.unpack(payload))


def decode_time_anchor_reply(payload: bytes) -> TimeAnchorReply:
    payload = bytes(payload)
    _check_len(payload, TIME_ANCHOR_REPLY_LEN, "time anchor reply")
    return TimeAnchorReply(*_ANCHOR_REPLY.unpack(payload))


def decode_time_anchor_request_frame(frame: Frame) -> TimeAnchorRequest:
    _check_type(frame, MSG_TIME_ANCHOR)
    return decode_time_anchor_request(frame.payload)


def decode_time_anchor_reply_frame(frame: Frame) -> TimeAnchorReply:
    _check_type(frame, MSG_TIME_ANCHOR)
    return decode_time_anchor_reply(frame.payload)


def encode_time_anchor_request_frame(req: TimeAnchorRequest) -> bytes:
    return Frame(msg_type=MSG_TIME_ANCHOR, payload=req.encode_payload()).encode()


def encode_time_anchor_reply_frame(rep: TimeAnchorReply) -> bytes:
    return Frame(msg_type=MSG_TIME_ANCHOR, payload=rep.encode_payload()).encode()


# CONFIG_SET / CONFIG_STATE ---------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    mode: int
    payload_format: int
    ppg_rate_hz: tuple[int, int, int, int]  # night, day, workout, raw
    burst_period_s: int
    burst_len_s: int
    led_mask: int
    led_green_ma: int
    led_red_ma: int
    led_ir_ma: int
    wear_ppg_dc: int
    wear_motion_thr: int
    wear_probe_period_ms: int

    def validate(self) -> None:
        if not isinstance(self.mode, int) or not 0 <= self.mode <= MODE_RAW:
            raise _invalid("mode", 0)
        if not isinstance(self.payload_format, int) or not (
            0 <= self.payload_format <= PAYLOAD_FORMAT_STREAM_RAW
        ):
            raise _invalid("payload_format", 1)
        if len(self.ppg_rate_hz) != 4:
            raise _invalid("ppg_rate_hz", 2)
        for i, rate in enumerate(self.ppg_rate_hz):
            _check_uint(rate, 16, "ppg_rate_hz", 2 + 2 * i)
            if rate > MAX_PPG_RATE_HZ:
                raise _invalid("ppg_rate_hz", 2 + 2 * i)
        _check_uint(self.burst_period_s, 16, "burst_period_s", 10)
        _check_uint(self.burst_len_s, 16, "burst_len_s", 12)
        if self.burst_len_s > self.burst_period_s:
            raise _invalid("burst_len_s", 12)
        if _check_uint(self.led_mask, 8, "led_mask", 14) > 0x07:
            raise _invalid("led_mask", 14)
        _check_uint(self.led_green_ma, 8, "led_green_ma", 15)
        _check_uint(self.led_red_ma, 8, "led_red_ma", 16)
        _check_uint(self.led_ir_ma, 8, "led_ir_ma", 17)
        _check_uint(self.wear_ppg_dc, 32, "wear_ppg_dc", 18)
        _check_uint(self.wear_motion_thr, 16, "wear_motion_thr", 22)
        _check_uint(self.wear_probe_period_ms, 16, "wear_probe_period_ms", 24)

    def encode_payload(self) -> bytes:
        self.validate()
        return _CONFIG.pack(
            self.mode,
            self.payload_format,
            *self.ppg_rate_hz,
            self.burst_period_s,
            self.burst_len_s,
            self.led_mask,
            self.led_green_ma,
            self.led_red_ma,
            self.led_ir_ma,
            self.wear_ppg_dc,
            self.wear_motion_thr,
            self.wear_probe_period_ms,
        )


def decode_config(payload: bytes) -> Config:
    payload = bytes(payload)
    _check_len(payload, CONFIG_PAYLOAD_LEN, "config")
    f = _CONFIG.unpack(payload)
    cfg = Config(
        mode=f[0],
        payload_format=f[1],
        ppg_rate_hz=(f[2], f[3], f[4], f[5]),
        burst_period_s=f[6],
        burst_len_s=f[7],
        led_mask=f[8],
        led_green_ma=f[9],
        led_red_ma=f[10],
        led_ir_ma=f[11],
        wear_ppg_dc=f[12],
        wear_motion_thr=f[13],
        wear_probe_period_ms=f[14],
    )
    cfg.validate()
    return cfg


def decode_config_set_frame(frame: Frame) -> Config:
    _check_type(frame, MSG_CONFIG_SET)
    return decode_config(frame.payload)


def decode_config_state_frame(frame: Frame) -> Config:
    _check_type(frame, MSG_CONFIG_STATE)
    return decode_config(frame.payload)


def encode_config_set_frame(cfg: Config) -> bytes:
    return Frame(msg_type=MSG_CONFIG_SET, payload=cfg.encode_payload()).encode()


def encode_config_state_frame(cfg: Config) -> bytes:
    return Frame(msg_type=MSG_CONFIG_STATE, payload=cfg.encode_payload()).encode()


def encode_config_query_frame() -> bytes:
    return Frame(msg_type=MSG_CONFIG_STATE, payload=b"").encode()


# BATTERY ---------------------------------------------------------------------------------------

_CHARGING_VALUES = (
    CHARGING_NOT_CHARGING,
    CHARGING_CHARGING,
    CHARGING_COMPLETE,
    CHARGING_FAULT,
    CHARGING_UNKNOWN,
)


@dataclass(frozen=True)
class Battery:
    voltage_mv: int
    charging: int
    percent: int
    avg_current_ua: tuple[int, int, int, int]  # night, day, workout, raw

    def validate(self) -> None:
        _check_uint(self.voltage_mv, 16, "voltage_mv", 0)
        if self.charging not in _CHARGING_VALUES:
            raise _invalid("charging", 2)
        if not isinstance(self.percent, int) or not (
            0 <= self.percent <= 100 or self.percent == PERCENT_UNKNOWN
        ):
            raise _invalid("percent", 3)
        if len(self.avg_current_ua) != 4:
            raise _invalid("avg_current_ua", 4)
        for i, cur in enumerate(self.avg_current_ua):
            _check_uint(cur, 16, "avg_current_ua", 4 + 2 * i)

    def encode_payload(self) -> bytes:
        self.validate()
        return _BATTERY.pack(self.voltage_mv, self.charging, self.percent, *self.avg_current_ua)


def decode_battery(payload: bytes) -> Battery:
    payload = bytes(payload)
    _check_len(payload, BATTERY_PAYLOAD_LEN, "battery")
    f = _BATTERY.unpack(payload)
    bat = Battery(voltage_mv=f[0], charging=f[1], percent=f[2], avg_current_ua=(f[3], f[4], f[5], f[6]))
    bat.validate()
    return bat


def decode_battery_frame(frame: Frame) -> Battery:
    _check_type(frame, MSG_BATTERY)
    return decode_battery(frame.payload)


def encode_battery_frame(bat: Battery) -> bytes:
    return Frame(msg_type=MSG_BATTERY, payload=bat.encode_payload()).encode()


def encode_battery_query_frame() -> bytes:
    return Frame(msg_type=MSG_BATTERY, payload=b"").encode()
