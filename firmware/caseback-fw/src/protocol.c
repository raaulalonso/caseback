/* SPDX-License-Identifier: Apache-2.0 */
/* The rest of firmware/ is under FSL-1.1-ALv2 (firmware/LICENSE). */
#include "protocol.h"

#include <string.h>

static void put_u16(uint8_t *p, uint16_t v)
{
	p[0] = (uint8_t)(v & 0xFFu);
	p[1] = (uint8_t)(v >> 8);
}

static void put_u32(uint8_t *p, uint32_t v)
{
	put_u16(p, (uint16_t)(v & 0xFFFFu));
	put_u16(p + 2, (uint16_t)(v >> 16));
}

static void put_u64(uint8_t *p, uint64_t v)
{
	put_u32(p, (uint32_t)(v & 0xFFFFFFFFu));
	put_u32(p + 4, (uint32_t)(v >> 32));
}

static uint16_t get_u16(const uint8_t *p)
{
	return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t get_u32(const uint8_t *p)
{
	return (uint32_t)get_u16(p) | ((uint32_t)get_u16(p + 2) << 16);
}

static uint64_t get_u64(const uint8_t *p)
{
	return (uint64_t)get_u32(p) | ((uint64_t)get_u32(p + 4) << 32);
}

uint16_t caseback_crc16_ccitt(const uint8_t *data, size_t len)
{
	uint16_t crc = 0xFFFFu;

	for (size_t i = 0; i < len; i++) {
		crc ^= (uint16_t)data[i] << 8;
		for (int b = 0; b < 8; b++) {
			if (crc & 0x8000u) {
				crc = (uint16_t)((crc << 1) ^ 0x1021u);
			} else {
				crc = (uint16_t)(crc << 1);
			}
		}
	}
	return crc;
}

int caseback_encode_frame(uint8_t msg_type, const uint8_t *payload, uint16_t payload_len,
		       uint8_t *out, size_t out_cap, size_t *out_len)
{
	const size_t total = CASEBACK_HEADER_LEN + (size_t)payload_len + CASEBACK_CRC_LEN;

	if (!out || !out_len || (!payload && payload_len > 0)) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	if (payload_len > CASEBACK_MAX_PAYLOAD) {
		return CASEBACK_ERR_PAYLOAD_TOO_LONG;
	}
	if (out_cap < total) {
		return CASEBACK_ERR_BUFFER_TOO_SMALL;
	}
	out[0] = CASEBACK_MAGIC;
	out[1] = CASEBACK_PROTO_VER;
	out[2] = msg_type;
	put_u16(&out[3], payload_len);
	if (payload_len) {
		memcpy(&out[CASEBACK_HEADER_LEN], payload, payload_len);
	}
	put_u16(&out[CASEBACK_HEADER_LEN + payload_len],
		caseback_crc16_ccitt(out, CASEBACK_HEADER_LEN + payload_len));
	*out_len = total;
	return CASEBACK_OK;
}

int caseback_decode_frame(const uint8_t *data, size_t len, struct caseback_frame *frame)
{
	if (!frame || (!data && len > 0)) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	if (len < 1) {
		return CASEBACK_ERR_TRUNCATED;
	}
	if (data[0] != CASEBACK_MAGIC) {
		return CASEBACK_ERR_BAD_MAGIC;
	}
	if (len < 2) {
		return CASEBACK_ERR_TRUNCATED;
	}
	if (data[1] != CASEBACK_PROTO_VER) {
		return CASEBACK_ERR_UNSUPPORTED_VERSION;
	}
	if (len < CASEBACK_HEADER_LEN) {
		return CASEBACK_ERR_TRUNCATED;
	}
	uint16_t payload_len = get_u16(&data[3]);

	if (payload_len > CASEBACK_MAX_PAYLOAD) {
		return CASEBACK_ERR_PAYLOAD_TOO_LONG;
	}
	const size_t expected = CASEBACK_HEADER_LEN + (size_t)payload_len + CASEBACK_CRC_LEN;

	if (len < expected) {
		return CASEBACK_ERR_TRUNCATED;
	}
	if (len > expected) {
		return CASEBACK_ERR_LENGTH_MISMATCH;
	}
	if (get_u16(&data[expected - CASEBACK_CRC_LEN]) !=
	    caseback_crc16_ccitt(data, expected - CASEBACK_CRC_LEN)) {
		return CASEBACK_ERR_BAD_CRC;
	}
	frame->proto_ver = data[1];
	frame->msg_type = data[2];
	frame->payload_len = payload_len;
	memcpy(frame->payload, &data[CASEBACK_HEADER_LEN], payload_len);
	return CASEBACK_OK;
}

/* helpers ---------------------------------------------------------------------------------- */

static void set_detail(uint8_t *detail, uint8_t v)
{
	if (detail) {
		*detail = v;
	}
}

static int bad_field(uint8_t *detail, uint8_t offset)
{
	set_detail(detail, offset);
	return CASEBACK_ERR_INVALID_FIELD;
}

static int check_out(uint8_t *out, size_t cap, size_t *out_len, size_t need)
{
	if (!out || !out_len) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	if (cap < need) {
		return CASEBACK_ERR_BUFFER_TOO_SMALL;
	}
	return CASEBACK_OK;
}

static int check_in(const uint8_t *payload, size_t len, size_t want, const void *out, uint8_t *detail)
{
	if (!out || (!payload && len > 0)) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	if (len != want) {
		set_detail(detail, (uint8_t)(want > 255u ? 255u : want));
		return CASEBACK_ERR_BAD_PAYLOAD_LENGTH;
	}
	return CASEBACK_OK;
}

static int check_frame(const struct caseback_frame *frame, uint8_t msg_type, const void *out)
{
	if (!frame || !out) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	return frame->msg_type == msg_type ? CASEBACK_OK : CASEBACK_ERR_UNKNOWN_MSG_TYPE;
}

/* INFO ------------------------------------------------------------------------------------- */

int caseback_encode_info(const struct caseback_info *in, uint8_t *out, size_t cap, size_t *out_len)
{
	int rc = check_out(out, cap, out_len, CASEBACK_INFO_PAYLOAD_LEN);

	if (rc) {
		return rc;
	}
	if (!in) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	memcpy(out, in->device_id, CASEBACK_DEVICE_ID_LEN);
	put_u16(&out[8], in->hw_rev);
	put_u16(&out[10], in->fw_rev);
	put_u32(&out[12], in->capabilities);
	*out_len = CASEBACK_INFO_PAYLOAD_LEN;
	return CASEBACK_OK;
}

int caseback_decode_info(const uint8_t *payload, size_t len, struct caseback_info *out)
{
	int rc = check_in(payload, len, CASEBACK_INFO_PAYLOAD_LEN, out, NULL);

	if (rc) {
		return rc;
	}
	memcpy(out->device_id, payload, CASEBACK_DEVICE_ID_LEN);
	out->hw_rev = get_u16(&payload[8]);
	out->fw_rev = get_u16(&payload[10]);
	out->capabilities = get_u32(&payload[12]);
	return CASEBACK_OK;
}

int caseback_decode_info_frame(const struct caseback_frame *frame, struct caseback_info *out)
{
	int rc = check_frame(frame, CASEBACK_MSG_INFO_RESPONSE, out);

	return rc ? rc : caseback_decode_info(frame->payload, frame->payload_len, out);
}

/* ERROR ------------------------------------------------------------------------------------ */

int caseback_encode_error(const struct caseback_error_msg *in, uint8_t *out, size_t cap, size_t *out_len)
{
	int rc = check_out(out, cap, out_len, CASEBACK_ERROR_PAYLOAD_LEN);

	if (rc) {
		return rc;
	}
	if (!in) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	put_u16(&out[0], in->code);
	out[2] = in->msg_type;
	out[3] = in->detail;
	*out_len = CASEBACK_ERROR_PAYLOAD_LEN;
	return CASEBACK_OK;
}

int caseback_decode_error(const uint8_t *payload, size_t len, struct caseback_error_msg *out)
{
	int rc = check_in(payload, len, CASEBACK_ERROR_PAYLOAD_LEN, out, NULL);

	if (rc) {
		return rc;
	}
	out->code = get_u16(&payload[0]);
	out->msg_type = payload[2];
	out->detail = payload[3];
	return CASEBACK_OK;
}

int caseback_decode_error_frame(const struct caseback_frame *frame, struct caseback_error_msg *out)
{
	int rc = check_frame(frame, CASEBACK_MSG_ERROR, out);

	return rc ? rc : caseback_decode_error(frame->payload, frame->payload_len, out);
}

/* TIME_ANCHOR ------------------------------------------------------------------------------ */

int caseback_encode_time_anchor_request(const struct caseback_time_anchor_request *in, uint8_t *out,
				     size_t cap, size_t *out_len)
{
	int rc = check_out(out, cap, out_len, CASEBACK_TIME_ANCHOR_REQUEST_LEN);

	if (rc) {
		return rc;
	}
	if (!in) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	put_u64(out, in->utc_ms);
	*out_len = CASEBACK_TIME_ANCHOR_REQUEST_LEN;
	return CASEBACK_OK;
}

int caseback_decode_time_anchor_request(const uint8_t *payload, size_t len,
				     struct caseback_time_anchor_request *out)
{
	int rc = check_in(payload, len, CASEBACK_TIME_ANCHOR_REQUEST_LEN, out, NULL);

	if (rc) {
		return rc;
	}
	out->utc_ms = get_u64(payload);
	return CASEBACK_OK;
}

int caseback_decode_time_anchor_request_frame(const struct caseback_frame *frame,
					   struct caseback_time_anchor_request *out)
{
	int rc = check_frame(frame, CASEBACK_MSG_TIME_ANCHOR, out);

	return rc ? rc : caseback_decode_time_anchor_request(frame->payload, frame->payload_len, out);
}

int caseback_encode_time_anchor_reply(const struct caseback_time_anchor_reply *in, uint8_t *out,
				   size_t cap, size_t *out_len)
{
	int rc = check_out(out, cap, out_len, CASEBACK_TIME_ANCHOR_REPLY_LEN);

	if (rc) {
		return rc;
	}
	if (!in) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	put_u32(&out[0], in->boot_id);
	put_u64(&out[4], in->uptime_ms);
	*out_len = CASEBACK_TIME_ANCHOR_REPLY_LEN;
	return CASEBACK_OK;
}

int caseback_decode_time_anchor_reply(const uint8_t *payload, size_t len,
				   struct caseback_time_anchor_reply *out)
{
	int rc = check_in(payload, len, CASEBACK_TIME_ANCHOR_REPLY_LEN, out, NULL);

	if (rc) {
		return rc;
	}
	out->boot_id = get_u32(&payload[0]);
	out->uptime_ms = get_u64(&payload[4]);
	return CASEBACK_OK;
}

int caseback_decode_time_anchor_reply_frame(const struct caseback_frame *frame,
					 struct caseback_time_anchor_reply *out)
{
	int rc = check_frame(frame, CASEBACK_MSG_TIME_ANCHOR, out);

	return rc ? rc : caseback_decode_time_anchor_reply(frame->payload, frame->payload_len, out);
}

/* CONFIG ----------------------------------------------------------------------------------- */

int caseback_config_validate(const struct caseback_config *cfg, uint8_t *detail)
{
	if (!cfg) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	if (cfg->mode > CASEBACK_MODE_RAW) {
		return bad_field(detail, 0);
	}
	if (cfg->payload_format > CASEBACK_PAYLOAD_FORMAT_STREAM_RAW) {
		return bad_field(detail, 1);
	}
	for (unsigned int i = 0; i < 4; i++) {
		if (cfg->ppg_rate_hz[i] > CASEBACK_MAX_PPG_RATE_HZ) {
			return bad_field(detail, (uint8_t)(2 + 2 * i));
		}
	}
	if (cfg->burst_len_s > cfg->burst_period_s) {
		return bad_field(detail, 12);
	}
	if (cfg->led_mask > 0x07u) {
		return bad_field(detail, 14);
	}
	return CASEBACK_OK;
}

int caseback_encode_config(const struct caseback_config *in, uint8_t *out, size_t cap, size_t *out_len)
{
	int rc = check_out(out, cap, out_len, CASEBACK_CONFIG_PAYLOAD_LEN);

	if (rc) {
		return rc;
	}
	rc = caseback_config_validate(in, NULL);
	if (rc) {
		return rc;
	}
	out[0] = in->mode;
	out[1] = in->payload_format;
	for (unsigned int i = 0; i < 4; i++) {
		put_u16(&out[2 + 2 * i], in->ppg_rate_hz[i]);
	}
	put_u16(&out[10], in->burst_period_s);
	put_u16(&out[12], in->burst_len_s);
	out[14] = in->led_mask;
	out[15] = in->led_green_ma;
	out[16] = in->led_red_ma;
	out[17] = in->led_ir_ma;
	put_u32(&out[18], in->wear_ppg_dc);
	put_u16(&out[22], in->wear_motion_thr);
	put_u16(&out[24], in->wear_probe_period_ms);
	*out_len = CASEBACK_CONFIG_PAYLOAD_LEN;
	return CASEBACK_OK;
}

int caseback_decode_config(const uint8_t *payload, size_t len, struct caseback_config *out,
			uint8_t *detail)
{
	int rc = check_in(payload, len, CASEBACK_CONFIG_PAYLOAD_LEN, out, detail);

	if (rc) {
		return rc;
	}
	struct caseback_config cfg;

	cfg.mode = payload[0];
	cfg.payload_format = payload[1];
	for (unsigned int i = 0; i < 4; i++) {
		cfg.ppg_rate_hz[i] = get_u16(&payload[2 + 2 * i]);
	}
	cfg.burst_period_s = get_u16(&payload[10]);
	cfg.burst_len_s = get_u16(&payload[12]);
	cfg.led_mask = payload[14];
	cfg.led_green_ma = payload[15];
	cfg.led_red_ma = payload[16];
	cfg.led_ir_ma = payload[17];
	cfg.wear_ppg_dc = get_u32(&payload[18]);
	cfg.wear_motion_thr = get_u16(&payload[22]);
	cfg.wear_probe_period_ms = get_u16(&payload[24]);
	rc = caseback_config_validate(&cfg, detail);
	if (rc) {
		return rc;
	}
	*out = cfg;
	return CASEBACK_OK;
}

int caseback_decode_config_frame(const struct caseback_frame *frame, struct caseback_config *out,
			      uint8_t *detail)
{
	if (!frame || !out) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	if (frame->msg_type != CASEBACK_MSG_CONFIG_SET && frame->msg_type != CASEBACK_MSG_CONFIG_STATE) {
		return CASEBACK_ERR_UNKNOWN_MSG_TYPE;
	}
	return caseback_decode_config(frame->payload, frame->payload_len, out, detail);
}

/* BATTERY ---------------------------------------------------------------------------------- */

int caseback_battery_validate(const struct caseback_battery *bat, uint8_t *detail)
{
	if (!bat) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	if (bat->charging > CASEBACK_CHARGING_FAULT && bat->charging != CASEBACK_CHARGING_UNKNOWN) {
		return bad_field(detail, 2);
	}
	if (bat->percent > 100u && bat->percent != CASEBACK_PERCENT_UNKNOWN) {
		return bad_field(detail, 3);
	}
	return CASEBACK_OK;
}

int caseback_encode_battery(const struct caseback_battery *in, uint8_t *out, size_t cap, size_t *out_len)
{
	int rc = check_out(out, cap, out_len, CASEBACK_BATTERY_PAYLOAD_LEN);

	if (rc) {
		return rc;
	}
	rc = caseback_battery_validate(in, NULL);
	if (rc) {
		return rc;
	}
	put_u16(&out[0], in->voltage_mv);
	out[2] = in->charging;
	out[3] = in->percent;
	for (unsigned int i = 0; i < 4; i++) {
		put_u16(&out[4 + 2 * i], in->avg_current_ua[i]);
	}
	*out_len = CASEBACK_BATTERY_PAYLOAD_LEN;
	return CASEBACK_OK;
}

int caseback_decode_battery(const uint8_t *payload, size_t len, struct caseback_battery *out,
			 uint8_t *detail)
{
	int rc = check_in(payload, len, CASEBACK_BATTERY_PAYLOAD_LEN, out, detail);

	if (rc) {
		return rc;
	}
	struct caseback_battery bat;

	bat.voltage_mv = get_u16(&payload[0]);
	bat.charging = payload[2];
	bat.percent = payload[3];
	for (unsigned int i = 0; i < 4; i++) {
		bat.avg_current_ua[i] = get_u16(&payload[4 + 2 * i]);
	}
	rc = caseback_battery_validate(&bat, detail);
	if (rc) {
		return rc;
	}
	*out = bat;
	return CASEBACK_OK;
}

int caseback_decode_battery_frame(const struct caseback_frame *frame, struct caseback_battery *out,
			       uint8_t *detail)
{
	int rc = check_frame(frame, CASEBACK_MSG_BATTERY, out);

	return rc ? rc : caseback_decode_battery(frame->payload, frame->payload_len, out, detail);
}
