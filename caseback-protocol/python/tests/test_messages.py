import pytest

from caseback_protocol import golden
from caseback_protocol.constants import (
    CAP_ACCEL,
    CAP_DFU_SMP,
    CAP_ENCRYPTED_ONLY,
    CAP_IBI_LOG,
    CAP_PPG_RAW,
    CAP_PPG_SUMMARY,
    CAP_SPO2,
    CAP_TEMPERATURE,
    MSG_BATTERY,
    MSG_CONFIG_SET,
    MSG_CONFIG_STATE,
    MSG_ERROR,
    MSG_INFO_REQUEST,
    MSG_INFO_RESPONSE,
    MSG_TIME_ANCHOR,
)
from caseback_protocol.errors import ErrorCode, MessageError
from caseback_protocol.framing import Frame, decode_frame
from caseback_protocol.messages import (
    Battery,
    Config,
    ErrorMessage,
    InfoResponse,
    TimeAnchorReply,
    TimeAnchorRequest,
    decode_battery,
    decode_battery_frame,
    decode_config,
    decode_config_set_frame,
    decode_config_state_frame,
    decode_error,
    decode_error_frame,
    decode_info_response,
    decode_info_response_frame,
    decode_time_anchor_reply,
    decode_time_anchor_reply_frame,
    decode_time_anchor_request,
    decode_time_anchor_request_frame,
    encode_battery_frame,
    encode_config_set_frame,
    encode_error_frame,
    encode_info_request,
    encode_info_response_frame,
    encode_time_anchor_request_frame,
)


def err(fn, *args) -> MessageError:
    with pytest.raises(MessageError) as exc:
        fn(*args)
    return exc.value


def test_message_type_values():
    assert (MSG_INFO_REQUEST, MSG_INFO_RESPONSE, MSG_ERROR, MSG_TIME_ANCHOR) == (1, 2, 3, 4)
    assert (MSG_CONFIG_SET, MSG_CONFIG_STATE, MSG_BATTERY) == (0x20, 0x21, 0x22)


def test_capability_bit_values():
    assert [CAP_PPG_RAW, CAP_PPG_SUMMARY, CAP_ACCEL, CAP_SPO2, CAP_TEMPERATURE, CAP_DFU_SMP,
            CAP_IBI_LOG, CAP_ENCRYPTED_ONLY] == [1, 2, 4, 8, 16, 32, 64, 128]


def test_info_request_is_empty_payload():
    frame = decode_frame(encode_info_request())
    assert frame.msg_type == MSG_INFO_REQUEST
    assert frame.payload == b""


def test_info_response_payload_layout():
    resp = InfoResponse(device_id=bytes(range(1, 9)), hw_rev=0x0100, fw_rev=0x0002, capabilities=0b100001)
    payload = resp.encode_payload()
    assert payload == bytes(range(1, 9)) + b"\x00\x01" + b"\x02\x00" + b"\x21\x00\x00\x00"


def test_info_response_frame_roundtrip_and_type_check():
    frame = decode_frame(encode_info_response_frame(golden.INFO))
    assert decode_info_response_frame(frame) == golden.INFO
    assert err(decode_info_response_frame, decode_frame(encode_info_request())).code == ErrorCode.UNKNOWN_MSG_TYPE


def test_info_response_rejects_bad_lengths_and_ranges():
    for n in (0, 15, 17):
        assert err(decode_info_response, b"\x00" * n).code == ErrorCode.BAD_PAYLOAD_LENGTH
    assert err(InfoResponse(b"\x00" * 7, 0, 0, 0).encode_payload).code == ErrorCode.INVALID_FIELD
    assert err(InfoResponse(bytes(8), 0x10000, 0, 0).encode_payload).code == ErrorCode.INVALID_FIELD


def test_error_message_roundtrip_and_unknown_code():
    for msg in (golden.ERROR, golden.ERROR_UNKNOWN_CODE):
        frame = decode_frame(encode_error_frame(msg))
        assert decode_error_frame(frame) == msg
    assert decode_error(b"\x02\x01\x20\x0c") == ErrorMessage(ErrorCode.INVALID_FIELD, 0x20, 0x0C)
    assert err(decode_error, b"\x00" * 3).code == ErrorCode.BAD_PAYLOAD_LENGTH
    assert err(decode_error_frame, Frame(MSG_BATTERY, b"\x00" * 4)).code == ErrorCode.UNKNOWN_MSG_TYPE


def test_time_anchor_layouts():
    assert golden.ANCHOR_REQUEST.encode_payload() == bytes.fromhex("e6d5c4b3a2010000")
    assert golden.ANCHOR_REPLY.encode_payload() == bytes.fromhex("cefadec0a0b1c2d3e4000000")
    assert decode_time_anchor_request(golden.ANCHOR_REQUEST.encode_payload()) == golden.ANCHOR_REQUEST
    assert decode_time_anchor_reply(golden.ANCHOR_REPLY.encode_payload()) == golden.ANCHOR_REPLY
    frame = decode_frame(encode_time_anchor_request_frame(golden.ANCHOR_REQUEST))
    assert decode_time_anchor_request_frame(frame) == golden.ANCHOR_REQUEST
    assert err(decode_time_anchor_reply_frame, frame).code == ErrorCode.BAD_PAYLOAD_LENGTH
    assert err(decode_time_anchor_request, b"\x00" * 12).code == ErrorCode.BAD_PAYLOAD_LENGTH


def test_time_anchor_u64_range():
    assert TimeAnchorRequest(2**64 - 1).encode_payload() == b"\xff" * 8
    assert err(TimeAnchorRequest(2**64).encode_payload).code == ErrorCode.INVALID_FIELD
    assert err(TimeAnchorRequest(-1).encode_payload).code == ErrorCode.INVALID_FIELD
    assert TimeAnchorReply(0xFFFFFFFF, 0).encode_payload()[:4] == b"\xff" * 4


def test_config_layout_and_roundtrip():
    payload = golden.CONFIG_SET.encode_payload()
    assert len(payload) == 26
    assert payload.hex() == "0201" "1900c800" "64009001" "2c01" "1e00" "05" "2a1b21" "c9b70500" "f401" "e803"
    assert decode_config(payload) == golden.CONFIG_SET
    assert decode_config_set_frame(decode_frame(encode_config_set_frame(golden.CONFIG_SET))) == golden.CONFIG_SET
    frame = decode_frame(encode_config_set_frame(golden.CONFIG_SET))
    assert err(decode_config_state_frame, frame).code == ErrorCode.UNKNOWN_MSG_TYPE


@pytest.mark.parametrize(
    "offset,mutate",
    [
        (0, lambda p: p.__setitem__(0, 4)),  # mode
        (1, lambda p: p.__setitem__(1, 2)),  # payload_format
        (2, lambda p: p.__setitem__(slice(2, 4), (401).to_bytes(2, "little"))),  # night rate
        (8, lambda p: p.__setitem__(slice(8, 10), (65535).to_bytes(2, "little"))),  # raw rate
        (12, lambda p: p.__setitem__(slice(12, 14), (301).to_bytes(2, "little"))),  # burst_len > period
        (14, lambda p: p.__setitem__(14, 0x08)),  # led_mask reserved bit
    ],
)
def test_config_invalid_fields_report_offset(offset, mutate):
    payload = bytearray(golden.CONFIG_SET.encode_payload())
    mutate(payload)
    e = err(decode_config, bytes(payload))
    assert e.code == ErrorCode.INVALID_FIELD
    assert e.detail == offset


def test_config_continuous_day_requires_zero_burst_length():
    from dataclasses import replace

    ok = replace(golden.CONFIG_SET, burst_period_s=0, burst_len_s=0)
    assert decode_config(ok.encode_payload()) == ok
    assert err(replace(golden.CONFIG_SET, burst_period_s=0, burst_len_s=1).encode_payload).detail == 12


def test_config_length_check():
    for n in (0, 25, 27):
        assert err(decode_config, b"\x00" * n).code == ErrorCode.BAD_PAYLOAD_LENGTH


def test_battery_layout_and_roundtrip():
    payload = golden.BATTERY.encode_payload()
    assert payload.hex() == "ad0f0157" "d2005603" "2b1a8e3d"
    assert decode_battery(payload) == golden.BATTERY
    assert decode_battery_frame(decode_frame(encode_battery_frame(golden.BATTERY))) == golden.BATTERY


def test_battery_unknown_values_and_validation():
    unknown = Battery(0, 0xFF, 0xFF, (0xFFFF,) * 4)
    assert decode_battery(unknown.encode_payload()) == unknown
    for bad in (Battery(3900, 4, 50, (0,) * 4), Battery(3900, 1, 101, (0,) * 4)):
        assert err(bad.encode_payload).code == ErrorCode.INVALID_FIELD
    assert err(decode_battery, b"\x00" * 11).code == ErrorCode.BAD_PAYLOAD_LENGTH


def test_error_code_values():
    expect = {
        "TRUNCATED": 0x0001, "BAD_MAGIC": 0x0002, "UNSUPPORTED_VERSION": 0x0003,
        "PAYLOAD_TOO_LONG": 0x0004, "LENGTH_MISMATCH": 0x0005, "BAD_CRC": 0x0006,
        "UNKNOWN_MSG_TYPE": 0x0100, "BAD_PAYLOAD_LENGTH": 0x0101, "INVALID_FIELD": 0x0102,
        "UNSUPPORTED": 0x0103, "WRONG_DIRECTION": 0x0104, "LINK_NOT_ENCRYPTED": 0x0200,
        "BUSY": 0x0201, "BAD_STATE": 0x0202, "NO_SUCH_STREAM": 0x0203,
        "CURSOR_OUT_OF_RANGE": 0x0204, "INTERNAL": 0x0300, "BUFFER_TOO_SMALL": 0xF001,
        "NULL_ARGUMENT": 0xF002,
    }
    for name, value in expect.items():
        assert ErrorCode[name] == value
