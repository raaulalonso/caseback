from pathlib import Path

import pytest

from caseback_protocol import golden
from caseback_protocol.errors import ErrorCode, FrameError
from caseback_protocol.framing import decode_frame
from caseback_protocol.messages import (
    decode_battery_frame,
    decode_config_set_frame,
    decode_config_state_frame,
    decode_error_frame,
    decode_info_response_frame,
    decode_time_anchor_reply_frame,
    decode_time_anchor_request_frame,
)

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"


def manifest_entries():
    rows = []
    for line in (GOLDEN / "manifest.txt").read_text().splitlines():
        if line and not line.startswith("#"):
            rows.append(line.split())
    return rows


def test_every_bin_is_in_the_manifest_and_vice_versa():
    listed = {row[0] for row in manifest_entries()}
    assert listed == {p.name for p in GOLDEN.glob("*.bin")}


@pytest.mark.parametrize("row", manifest_entries(), ids=lambda r: r[0])
def test_decode_matches_manifest(row):
    data = (GOLDEN / row[0]).read_bytes()
    if row[1] == "ok":
        frame = decode_frame(data)
        assert frame.msg_type == int(row[2], 16)
        assert len(frame.payload) == int(row[3])
    else:
        with pytest.raises(FrameError) as exc:
            decode_frame(data)
        assert exc.value.code.name.lower() == row[1]


def test_message_level_decode_of_every_positive_golden():
    def load(name):
        return decode_frame((GOLDEN / f"{name}.bin").read_bytes())

    assert decode_info_response_frame(load("info_response")) == golden.INFO
    assert decode_error_frame(load("error")) == golden.ERROR
    assert decode_error_frame(load("error_unknown_code")) == golden.ERROR_UNKNOWN_CODE
    assert decode_time_anchor_request_frame(load("time_anchor_request")) == golden.ANCHOR_REQUEST
    assert decode_time_anchor_reply_frame(load("time_anchor_reply")) == golden.ANCHOR_REPLY
    assert decode_config_set_frame(load("config_set")) == golden.CONFIG_SET
    assert decode_config_state_frame(load("config_state")) == golden.CONFIG_STATE
    assert decode_battery_frame(load("battery")) == golden.BATTERY
    assert load("info_request").payload == b""
    assert load("config_query").payload == b"" and load("battery_query").payload == b""
    assert load("max_payload").payload == golden.MAX_PAYLOAD_BYTES
    assert load("a5_payload").payload == golden.A5_PAYLOAD


def test_golden_files_equal_generator_output():
    for name, data in golden.positive_frames().items():
        assert (GOLDEN / f"{name}.bin").read_bytes() == data
    for name, (data, _) in golden.negative_frames().items():
        assert (GOLDEN / f"{name}.bin").read_bytes() == data
    assert (GOLDEN / "manifest.txt").read_text() == golden.manifest()


def test_golden_values_are_distinct_and_high():
    # guards the fixture design: no two fields of a message share a value
    assert len(set(golden.INFO.device_id)) == 8
    assert len({golden.INFO.hw_rev, golden.INFO.fw_rev, golden.INFO.capabilities}) == 3
    cfg = golden.CONFIG_SET
    vals = [cfg.mode, cfg.payload_format, *cfg.ppg_rate_hz, cfg.burst_period_s, cfg.burst_len_s,
            cfg.led_mask, cfg.led_green_ma, cfg.led_red_ma, cfg.led_ir_ma, cfg.wear_ppg_dc,
            cfg.wear_motion_thr, cfg.wear_probe_period_ms]
    assert len(set(vals)) == len(vals)
    assert len(set(golden.BATTERY.avg_current_ua)) == 4
    assert ErrorCode.INVALID_FIELD == golden.ERROR.code
