/* SPDX-License-Identifier: Apache-2.0 */
/* The rest of firmware/ is under FSL-1.1-ALv2 (firmware/LICENSE). */
#pragma once

/* Caseback protocol v0.2 (caseback-protocol/spec). Little-endian, fixed layouts.
 * Implemented here: framing, INFO, ERROR, TIME_ANCHOR, CONFIG, BATTERY.
 * STREAM_DATA, STREAM_CONTROL and HISTORY_* are specified only.
 */

#include <stddef.h>
#include <stdint.h>

#define CASEBACK_MAGIC 0xA5u
#define CASEBACK_PROTO_VER 0x01u
#define CASEBACK_HEADER_LEN 5u
#define CASEBACK_CRC_LEN 2u
#define CASEBACK_MAX_FRAME 182u /* ATT_MTU 185 - 3 */
#define CASEBACK_MAX_PAYLOAD (CASEBACK_MAX_FRAME - CASEBACK_HEADER_LEN - CASEBACK_CRC_LEN) /* 175 */

/* Message types */
#define CASEBACK_MSG_INFO_REQUEST 0x01u
#define CASEBACK_MSG_INFO_RESPONSE 0x02u
#define CASEBACK_MSG_ERROR 0x03u
#define CASEBACK_MSG_TIME_ANCHOR 0x04u
#define CASEBACK_MSG_STREAM_DATA 0x10u
#define CASEBACK_MSG_STREAM_CONTROL 0x11u
#define CASEBACK_MSG_HISTORY_QUERY 0x12u
#define CASEBACK_MSG_HISTORY_ACK 0x13u
#define CASEBACK_MSG_CONFIG_SET 0x20u
#define CASEBACK_MSG_CONFIG_STATE 0x21u
#define CASEBACK_MSG_BATTERY 0x22u
#define CASEBACK_MSG_DFU_RESERVED_FIRST 0x30u /* 0x30..0x3F: standard SMP DFU */
#define CASEBACK_MSG_DFU_RESERVED_LAST 0x3Fu

/* Payload sizes */
#define CASEBACK_INFO_PAYLOAD_LEN 16u
#define CASEBACK_ERROR_PAYLOAD_LEN 4u
#define CASEBACK_TIME_ANCHOR_REQUEST_LEN 8u
#define CASEBACK_TIME_ANCHOR_REPLY_LEN 12u
#define CASEBACK_CONFIG_PAYLOAD_LEN 26u
#define CASEBACK_BATTERY_PAYLOAD_LEN 12u
#define CASEBACK_DEVICE_ID_LEN 8u

/* Capability bits (caseback-protocol/spec/messages.md); bits 8..31 reserved */
#define CASEBACK_CAP_NONE 0x00000000u
#define CASEBACK_CAP_PPG_RAW (1u << 0)
#define CASEBACK_CAP_PPG_SUMMARY (1u << 1)
#define CASEBACK_CAP_ACCEL (1u << 2)
#define CASEBACK_CAP_SPO2 (1u << 3)
#define CASEBACK_CAP_TEMPERATURE (1u << 4)
#define CASEBACK_CAP_DFU_SMP (1u << 5)
#define CASEBACK_CAP_IBI_LOG (1u << 6)
#define CASEBACK_CAP_ENCRYPTED_ONLY (1u << 7)

/* Config enums */
#define CASEBACK_MODE_NIGHT 0u
#define CASEBACK_MODE_DAY 1u
#define CASEBACK_MODE_WORKOUT 2u
#define CASEBACK_MODE_RAW 3u
#define CASEBACK_PAYLOAD_FORMAT_SUMMARY 0u
#define CASEBACK_PAYLOAD_FORMAT_STREAM_RAW 1u
#define CASEBACK_LED_GREEN (1u << 0)
#define CASEBACK_LED_RED (1u << 1)
#define CASEBACK_LED_IR (1u << 2)
#define CASEBACK_MAX_PPG_RATE_HZ 400u
#define CASEBACK_CHARGING_NOT_CHARGING 0u
#define CASEBACK_CHARGING_CHARGING 1u
#define CASEBACK_CHARGING_COMPLETE 2u
#define CASEBACK_CHARGING_FAULT 3u
#define CASEBACK_CHARGING_UNKNOWN 0xFFu
#define CASEBACK_PERCENT_UNKNOWN 0xFFu
#define CASEBACK_CURRENT_UNKNOWN 0xFFFFu

/* GATT (caseback-protocol/spec/gatt.md). Zephyr:
 * BT_UUID_128_ENCODE(CASEBACK_UUID_INFO_W32, CASEBACK_UUID_W1, CASEBACK_UUID_W2, CASEBACK_UUID_W3, CASEBACK_UUID_W48)
 */
#define CASEBACK_UUID_SERVICE_STR "decdc7df-2ecb-4d75-b44c-992dccdfca5b"
#define CASEBACK_UUID_INFO_STR "decdc7e0-2ecb-4d75-b44c-992dccdfca5b"
#define CASEBACK_UUID_CONTROL_STR "decdc7e1-2ecb-4d75-b44c-992dccdfca5b"
#define CASEBACK_UUID_DATA_STR "decdc7e2-2ecb-4d75-b44c-992dccdfca5b"
#define CASEBACK_UUID_SMP_SERVICE_STR "8d53dc1d-1db7-4cd3-868b-8a527460aa84"
#define CASEBACK_UUID_SMP_CHARACTERISTIC_STR "da2e7828-fbce-4e01-ae9e-261174997c48"
#define CASEBACK_UUID_SERVICE_W32 0xdecdc7dfu
#define CASEBACK_UUID_INFO_W32 0xdecdc7e0u
#define CASEBACK_UUID_CONTROL_W32 0xdecdc7e1u
#define CASEBACK_UUID_DATA_W32 0xdecdc7e2u
#define CASEBACK_UUID_W1 0x2ecb
#define CASEBACK_UUID_W2 0x4d75
#define CASEBACK_UUID_W3 0xb44c
#define CASEBACK_UUID_W48 0x992dccdfca5bull

#define CASEBACK_CONN_INTERVAL_MIN_MS 1000u
#define CASEBACK_CONN_INTERVAL_MAX_MS 1500u
#define CASEBACK_CONN_LATENCY 0u
#define CASEBACK_CONN_SUPERVISION_TIMEOUT_MS 6000u
#define CASEBACK_ATT_MTU_REQUESTED 247u

/* Return value of every codec function: 0 on success, otherwise an ErrorCode (spec/messages.md). */
enum caseback_error {
	CASEBACK_OK = 0x0000,
	CASEBACK_ERR_TRUNCATED = 0x0001,
	CASEBACK_ERR_BAD_MAGIC = 0x0002,
	CASEBACK_ERR_UNSUPPORTED_VERSION = 0x0003,
	CASEBACK_ERR_PAYLOAD_TOO_LONG = 0x0004,
	CASEBACK_ERR_LENGTH_MISMATCH = 0x0005,
	CASEBACK_ERR_BAD_CRC = 0x0006,
	CASEBACK_ERR_UNKNOWN_MSG_TYPE = 0x0100,
	CASEBACK_ERR_BAD_PAYLOAD_LENGTH = 0x0101,
	CASEBACK_ERR_INVALID_FIELD = 0x0102,
	CASEBACK_ERR_UNSUPPORTED = 0x0103,
	CASEBACK_ERR_WRONG_DIRECTION = 0x0104,
	CASEBACK_ERR_LINK_NOT_ENCRYPTED = 0x0200,
	CASEBACK_ERR_BUSY = 0x0201,
	CASEBACK_ERR_BAD_STATE = 0x0202,
	CASEBACK_ERR_NO_SUCH_STREAM = 0x0203,
	CASEBACK_ERR_CURSOR_OUT_OF_RANGE = 0x0204,
	CASEBACK_ERR_INTERNAL = 0x0300,
	/* local only, never sent on the wire */
	CASEBACK_ERR_BUFFER_TOO_SMALL = 0xF001,
	CASEBACK_ERR_NULL_ARGUMENT = 0xF002,
};

struct caseback_frame {
	uint8_t msg_type;
	uint8_t proto_ver;
	uint16_t payload_len;
	uint8_t payload[CASEBACK_MAX_PAYLOAD];
};

uint16_t caseback_crc16_ccitt(const uint8_t *data, size_t len);

/* Decode order: magic, version, oversize, truncated, length mismatch, CRC. */
int caseback_encode_frame(uint8_t msg_type, const uint8_t *payload, uint16_t payload_len,
		       uint8_t *out, size_t out_cap, size_t *out_len);
int caseback_decode_frame(const uint8_t *data, size_t len, struct caseback_frame *frame);

struct caseback_info {
	uint8_t device_id[CASEBACK_DEVICE_ID_LEN];
	uint16_t hw_rev;
	uint16_t fw_rev;
	uint32_t capabilities;
};

struct caseback_error_msg {
	uint16_t code; /* enum caseback_error, or any u16 from a newer peer */
	uint8_t msg_type;
	uint8_t detail;
};

struct caseback_time_anchor_request {
	uint64_t utc_ms;
};

struct caseback_time_anchor_reply {
	uint32_t boot_id;
	uint64_t uptime_ms;
};

struct caseback_config {
	uint8_t mode;
	uint8_t payload_format;
	uint16_t ppg_rate_hz[4]; /* night, day, workout, raw */
	uint16_t burst_period_s;
	uint16_t burst_len_s;
	uint8_t led_mask;
	uint8_t led_green_ma;
	uint8_t led_red_ma;
	uint8_t led_ir_ma;
	uint32_t wear_ppg_dc;
	uint16_t wear_motion_thr;
	uint16_t wear_probe_period_ms;
};

struct caseback_battery {
	uint16_t voltage_mv;
	uint8_t charging;
	uint8_t percent;
	uint16_t avg_current_ua[4]; /* night, day, workout, raw */
};

/* Payload codecs. Encoders write exactly the fixed payload size to `out`; decoders take the
 * payload of a frame. `_frame` decoders also check msg_type. `detail` (nullable) receives the payload
 * offset of the first invalid field, or the expected length for a bad length.
 */
int caseback_encode_info(const struct caseback_info *in, uint8_t *out, size_t cap, size_t *out_len);
int caseback_decode_info(const uint8_t *payload, size_t len, struct caseback_info *out);
int caseback_decode_info_frame(const struct caseback_frame *frame, struct caseback_info *out);

int caseback_encode_error(const struct caseback_error_msg *in, uint8_t *out, size_t cap, size_t *out_len);
int caseback_decode_error(const uint8_t *payload, size_t len, struct caseback_error_msg *out);
int caseback_decode_error_frame(const struct caseback_frame *frame, struct caseback_error_msg *out);

int caseback_encode_time_anchor_request(const struct caseback_time_anchor_request *in, uint8_t *out,
				     size_t cap, size_t *out_len);
int caseback_decode_time_anchor_request(const uint8_t *payload, size_t len,
				     struct caseback_time_anchor_request *out);
int caseback_decode_time_anchor_request_frame(const struct caseback_frame *frame,
					   struct caseback_time_anchor_request *out);
int caseback_encode_time_anchor_reply(const struct caseback_time_anchor_reply *in, uint8_t *out,
				   size_t cap, size_t *out_len);
int caseback_decode_time_anchor_reply(const uint8_t *payload, size_t len,
				   struct caseback_time_anchor_reply *out);
int caseback_decode_time_anchor_reply_frame(const struct caseback_frame *frame,
					 struct caseback_time_anchor_reply *out);

int caseback_config_validate(const struct caseback_config *cfg, uint8_t *detail);
int caseback_encode_config(const struct caseback_config *in, uint8_t *out, size_t cap, size_t *out_len);
int caseback_decode_config(const uint8_t *payload, size_t len, struct caseback_config *out,
			uint8_t *detail);
/* accepts CONFIG_SET and CONFIG_STATE */
int caseback_decode_config_frame(const struct caseback_frame *frame, struct caseback_config *out,
			      uint8_t *detail);

int caseback_battery_validate(const struct caseback_battery *bat, uint8_t *detail);
int caseback_encode_battery(const struct caseback_battery *in, uint8_t *out, size_t cap, size_t *out_len);
int caseback_decode_battery(const uint8_t *payload, size_t len, struct caseback_battery *out,
			 uint8_t *detail);
int caseback_decode_battery_frame(const struct caseback_frame *frame, struct caseback_battery *out,
			       uint8_t *detail);
