/* SPDX-License-Identifier: Apache-2.0 */
/* The rest of firmware/ is under FSL-1.1-ALv2 (firmware/LICENSE). */
/* Host-side test for src/protocol.c against the shared golden fixtures.
 *
 * Build & run (from firmware/caseback-fw):
 *   cc -Wall -Wextra -Werror -Iinclude -fsanitize=address,undefined \
 *      -o /tmp/test_protocol tests/test_protocol.c src/protocol.c
 *   /tmp/test_protocol ../../caseback-protocol/fixtures/golden
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "protocol.h"

static int failures;
static int checks;

#define CHECK(cond)                                                            \
	do {                                                                   \
		checks++;                                                      \
		if (!(cond)) {                                                 \
			printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
			failures++;                                            \
		}                                                              \
	} while (0)

#define MAX_FILE 512

static size_t load(const char *dir, const char *name, uint8_t *buf, size_t cap)
{
	char path[512];

	snprintf(path, sizeof(path), "%s/%s", dir, name);
	FILE *f = fopen(path, "rb");

	if (!f) {
		printf("FAIL cannot open %s\n", path);
		exit(2);
	}
	size_t n = fread(buf, 1, cap, f);

	fclose(f);
	return n;
}

static int error_from_name(const char *name)
{
	static const struct {
		const char *name;
		int code;
	} table[] = {
		{"truncated", CASEBACK_ERR_TRUNCATED},
		{"bad_magic", CASEBACK_ERR_BAD_MAGIC},
		{"unsupported_version", CASEBACK_ERR_UNSUPPORTED_VERSION},
		{"payload_too_long", CASEBACK_ERR_PAYLOAD_TOO_LONG},
		{"length_mismatch", CASEBACK_ERR_LENGTH_MISMATCH},
		{"bad_crc", CASEBACK_ERR_BAD_CRC},
	};

	for (size_t i = 0; i < sizeof(table) / sizeof(table[0]); i++) {
		if (strcmp(table[i].name, name) == 0) {
			return table[i].code;
		}
	}
	return -1;
}

static void test_crc_check_value(void)
{
	CHECK(caseback_crc16_ccitt((const uint8_t *)"123456789", 9) == 0x29B1);
	CHECK(caseback_crc16_ccitt(NULL, 0) == 0xFFFF);
}

static void test_limits_and_codes(void)
{
	CHECK(CASEBACK_MAX_PAYLOAD == 175u);
	CHECK(CASEBACK_MAX_FRAME == 182u);
	CHECK(CASEBACK_ERR_TRUNCATED == 1 && CASEBACK_ERR_BAD_MAGIC == 2 && CASEBACK_ERR_UNSUPPORTED_VERSION == 3);
	CHECK(CASEBACK_ERR_PAYLOAD_TOO_LONG == 4 && CASEBACK_ERR_LENGTH_MISMATCH == 5 && CASEBACK_ERR_BAD_CRC == 6);
	CHECK(CASEBACK_ERR_UNKNOWN_MSG_TYPE == 0x100 && CASEBACK_ERR_BAD_PAYLOAD_LENGTH == 0x101);
	CHECK(CASEBACK_ERR_INVALID_FIELD == 0x102 && CASEBACK_ERR_CURSOR_OUT_OF_RANGE == 0x204);
	CHECK(CASEBACK_ERR_BUFFER_TOO_SMALL == 0xF001 && CASEBACK_ERR_NULL_ARGUMENT == 0xF002);
	CHECK(CASEBACK_CAP_PPG_RAW == 1u && CASEBACK_CAP_PPG_SUMMARY == 2u && CASEBACK_CAP_ACCEL == 4u);
	CHECK(CASEBACK_CAP_SPO2 == 8u && CASEBACK_CAP_TEMPERATURE == 16u && CASEBACK_CAP_DFU_SMP == 32u);
	CHECK(CASEBACK_CAP_IBI_LOG == 64u && CASEBACK_CAP_ENCRYPTED_ONLY == 128u);
	CHECK(strcmp(CASEBACK_UUID_SERVICE_STR, "decdc7df-2ecb-4d75-b44c-992dccdfca5b") == 0);
	CHECK(strcmp(CASEBACK_UUID_CONTROL_STR, "decdc7e1-2ecb-4d75-b44c-992dccdfca5b") == 0);
}

/* Every manifest line: "ok" files decode with the listed type and length, others give the listed error. */
static void test_manifest(const char *dir)
{
	uint8_t data[MAX_FILE];
	char mpath[512];
	char line[256];
	int entries = 0;

	snprintf(mpath, sizeof(mpath), "%s/manifest.txt", dir);
	FILE *m = fopen(mpath, "r");

	if (!m) {
		printf("FAIL cannot open %s\n", mpath);
		exit(2);
	}
	while (fgets(line, sizeof(line), m)) {
		char name[128], status[64];
		unsigned int type = 0, plen = 0;
		struct caseback_frame fr;

		if (line[0] == '#' || line[0] == '\n') {
			continue;
		}
		int fields = sscanf(line, "%127s %63s %x %u", name, status, &type, &plen);

		CHECK(fields >= 2);
		size_t n = load(dir, name, data, sizeof(data));

		entries++;
		if (strcmp(status, "ok") == 0) {
			uint8_t re[MAX_FILE];
			size_t re_len = 0;

			CHECK(fields == 4);
			CHECK(caseback_decode_frame(data, n, &fr) == CASEBACK_OK);
			CHECK(fr.msg_type == type && fr.payload_len == plen && fr.proto_ver == 1);
			CHECK(caseback_encode_frame(fr.msg_type, fr.payload, fr.payload_len, re, sizeof(re),
						 &re_len) == CASEBACK_OK);
			CHECK(re_len == n && memcmp(re, data, n) == 0);
		} else {
			int want = error_from_name(status);

			if (want < 0) {
				printf("FAIL unknown error name %s in manifest\n", status);
				failures++;
			}
			if (caseback_decode_frame(data, n, &fr) != want) {
				printf("FAIL %s: expected %s\n", name, status);
				failures++;
			}
			checks++;
		}
	}
	fclose(m);
	CHECK(entries >= 20);
}

static struct caseback_frame load_frame(const char *dir, const char *name)
{
	uint8_t data[MAX_FILE];
	struct caseback_frame fr;
	size_t n = load(dir, name, data, sizeof(data));

	if (caseback_decode_frame(data, n, &fr) != CASEBACK_OK) {
		printf("FAIL %s does not decode\n", name);
		exit(2);
	}
	return fr;
}

/* Byte-for-byte the hand-derived vectors of spec/messages.md. */
static const uint8_t V_INFO_RESPONSE[] = {0xA5, 0x01, 0x02, 0x10, 0x00, 0x8B, 0x9C, 0xAD, 0xBE, 0xCF, 0xD0,
					   0xE1, 0xF2, 0x02, 0x81, 0x04, 0x93, 0xC3, 0x00, 0x00, 0x00,
					   0x82, 0xBB};
static const uint8_t V_ERROR[] = {0xA5, 0x01, 0x03, 0x04, 0x00, 0x02, 0x01, 0x20, 0x0C, 0x32, 0xF3};
static const uint8_t V_ANCHOR_REQ[] = {0xA5, 0x01, 0x04, 0x08, 0x00, 0xE6, 0xD5, 0xC4,
				       0xB3, 0xA2, 0x01, 0x00, 0x00, 0x1B, 0x68};
static const uint8_t V_ANCHOR_REPLY[] = {0xA5, 0x01, 0x04, 0x0C, 0x00, 0xCE, 0xFA, 0xDE, 0xC0,
					 0xA0, 0xB1, 0xC2, 0xD3, 0xE4, 0x00, 0x00, 0x00, 0x26, 0x9F};

static void check_file_and_encode(const char *dir, const char *name, uint8_t type,
				  const uint8_t *payload, size_t plen, const uint8_t *spec,
				  size_t spec_len)
{
	uint8_t golden[MAX_FILE], out[MAX_FILE];
	size_t n = load(dir, name, golden, sizeof(golden));
	size_t out_len = 0;

	CHECK(caseback_encode_frame(type, payload, (uint16_t)plen, out, sizeof(out), &out_len) == CASEBACK_OK);
	CHECK(out_len == n && memcmp(out, golden, n) == 0);
	if (spec) {
		CHECK(spec_len == n && memcmp(spec, golden, n) == 0);
	}
}

static void test_messages(const char *dir)
{
	uint8_t p[64];
	size_t len;
	struct caseback_frame fr;

	/* INFO */
	struct caseback_info info_want = {
		.device_id = {0x8B, 0x9C, 0xAD, 0xBE, 0xCF, 0xD0, 0xE1, 0xF2},
		.hw_rev = 0x8102,
		.fw_rev = 0x9304,
		.capabilities = CASEBACK_CAP_PPG_RAW | CASEBACK_CAP_PPG_SUMMARY | CASEBACK_CAP_IBI_LOG |
				CASEBACK_CAP_ENCRYPTED_ONLY,
	};
	struct caseback_info info;

	fr = load_frame(dir, "info_response.bin");
	CHECK(caseback_decode_info_frame(&fr, &info) == CASEBACK_OK);
	CHECK(memcmp(&info, &info_want, sizeof(info)) == 0);
	CHECK(caseback_encode_info(&info_want, p, sizeof(p), &len) == CASEBACK_OK && len == 16);
	check_file_and_encode(dir, "info_response.bin", CASEBACK_MSG_INFO_RESPONSE, p, len, V_INFO_RESPONSE,
			      sizeof(V_INFO_RESPONSE));
	fr = load_frame(dir, "info_request.bin");
	CHECK(fr.msg_type == CASEBACK_MSG_INFO_REQUEST && fr.payload_len == 0);
	CHECK(caseback_decode_info_frame(&fr, &info) == CASEBACK_ERR_UNKNOWN_MSG_TYPE);
	check_file_and_encode(dir, "info_request.bin", CASEBACK_MSG_INFO_REQUEST, NULL, 0, NULL, 0);
	CHECK(caseback_decode_info(p, 15, &info) == CASEBACK_ERR_BAD_PAYLOAD_LENGTH);

	/* ERROR */
	struct caseback_error_msg err_want = {CASEBACK_ERR_INVALID_FIELD, 0x20, 0x0C};
	struct caseback_error_msg err;

	fr = load_frame(dir, "error.bin");
	CHECK(caseback_decode_error_frame(&fr, &err) == CASEBACK_OK);
	CHECK(err.code == 0x0102 && err.msg_type == 0x20 && err.detail == 0x0C);
	CHECK(caseback_encode_error(&err_want, p, sizeof(p), &len) == CASEBACK_OK && len == 4);
	check_file_and_encode(dir, "error.bin", CASEBACK_MSG_ERROR, p, len, V_ERROR, sizeof(V_ERROR));
	fr = load_frame(dir, "error_unknown_code.bin");
	CHECK(caseback_decode_error_frame(&fr, &err) == CASEBACK_OK);
	CHECK(err.code == 0x9ABC && err.msg_type == 0xC7 && err.detail == 0xE1);

	/* TIME_ANCHOR */
	struct caseback_time_anchor_request rq;
	struct caseback_time_anchor_request rq_want = {0x000001A2B3C4D5E6ull};
	struct caseback_time_anchor_reply rp;
	struct caseback_time_anchor_reply rp_want = {0xC0DEFACEu, 0x000000E4D3C2B1A0ull};

	fr = load_frame(dir, "time_anchor_request.bin");
	CHECK(caseback_decode_time_anchor_request_frame(&fr, &rq) == CASEBACK_OK && rq.utc_ms == rq_want.utc_ms);
	CHECK(caseback_decode_time_anchor_reply_frame(&fr, &rp) == CASEBACK_ERR_BAD_PAYLOAD_LENGTH);
	CHECK(caseback_encode_time_anchor_request(&rq_want, p, sizeof(p), &len) == CASEBACK_OK && len == 8);
	check_file_and_encode(dir, "time_anchor_request.bin", CASEBACK_MSG_TIME_ANCHOR, p, len, V_ANCHOR_REQ,
			      sizeof(V_ANCHOR_REQ));
	fr = load_frame(dir, "time_anchor_reply.bin");
	CHECK(caseback_decode_time_anchor_reply_frame(&fr, &rp) == CASEBACK_OK);
	CHECK(rp.boot_id == rp_want.boot_id && rp.uptime_ms == rp_want.uptime_ms);
	CHECK(caseback_encode_time_anchor_reply(&rp_want, p, sizeof(p), &len) == CASEBACK_OK && len == 12);
	check_file_and_encode(dir, "time_anchor_reply.bin", CASEBACK_MSG_TIME_ANCHOR, p, len, V_ANCHOR_REPLY,
			      sizeof(V_ANCHOR_REPLY));

	/* CONFIG */
	struct caseback_config set_want = {
		.mode = 2, .payload_format = 1, .ppg_rate_hz = {25, 200, 100, 400},
		.burst_period_s = 300, .burst_len_s = 30, .led_mask = 5, .led_green_ma = 42,
		.led_red_ma = 27, .led_ir_ma = 33, .wear_ppg_dc = 0x0005B7C9u, .wear_motion_thr = 500,
		.wear_probe_period_ms = 1000,
	};
	struct caseback_config state_want = {
		.mode = 1, .payload_format = 0, .ppg_rate_hz = {48, 32, 128, 400},
		.burst_period_s = 600, .burst_len_s = 45, .led_mask = 7, .led_green_ma = 60,
		.led_red_ma = 52, .led_ir_ma = 41, .wear_ppg_dc = 0x0007FFFFu, .wear_motion_thr = 3000,
		.wear_probe_period_ms = 5000,
	};
	struct caseback_config cfg;
	uint8_t detail = 0xEE;

	fr = load_frame(dir, "config_set.bin");
	CHECK(fr.msg_type == CASEBACK_MSG_CONFIG_SET);
	CHECK(caseback_decode_config_frame(&fr, &cfg, &detail) == CASEBACK_OK);
	CHECK(cfg.mode == 2 && cfg.payload_format == 1 && cfg.ppg_rate_hz[0] == 25 && cfg.ppg_rate_hz[2] == 100);
	CHECK(cfg.burst_len_s == 30 && cfg.led_mask == 5 && cfg.led_green_ma == 42 && cfg.led_red_ma == 27);
	CHECK(cfg.wear_ppg_dc == 0x0005B7C9u);
	CHECK(cfg.ppg_rate_hz[1] == 200 && cfg.ppg_rate_hz[3] == 400 && cfg.burst_period_s == 300);
	CHECK(cfg.led_ir_ma == 33 && cfg.wear_motion_thr == 500 && cfg.wear_probe_period_ms == 1000);
	CHECK(caseback_encode_config(&set_want, p, sizeof(p), &len) == CASEBACK_OK && len == 26);
	check_file_and_encode(dir, "config_set.bin", CASEBACK_MSG_CONFIG_SET, p, len, NULL, 0);
	fr = load_frame(dir, "config_state.bin");
	CHECK(caseback_decode_config_frame(&fr, &cfg, &detail) == CASEBACK_OK);
	CHECK(cfg.mode == 1 && cfg.ppg_rate_hz[2] == 128 && cfg.wear_ppg_dc == 0x7FFFFu);
	CHECK(caseback_encode_config(&state_want, p, sizeof(p), &len) == CASEBACK_OK);
	check_file_and_encode(dir, "config_state.bin", CASEBACK_MSG_CONFIG_STATE, p, len, NULL, 0);
	fr = load_frame(dir, "config_query.bin");
	CHECK(fr.msg_type == CASEBACK_MSG_CONFIG_STATE && fr.payload_len == 0);
	check_file_and_encode(dir, "config_query.bin", CASEBACK_MSG_CONFIG_STATE, NULL, 0, NULL, 0);

	/* invalid config fields, with the offset reported */
	{
		static const struct {
			unsigned int offset;
			uint8_t value;
			unsigned int at;
		} bad[] = {{0, 4, 0}, {1, 2, 1}, {2, 0x91, 3}, {14, 0x08, 14}};
		uint8_t pl[26];

		CHECK(caseback_encode_config(&set_want, pl, sizeof(pl), &len) == CASEBACK_OK);
		for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
			uint8_t m[26];

			memcpy(m, pl, sizeof(m));
			m[bad[i].at] = bad[i].value; /* rate high byte 0x91 -> 0x91xx > 400 */
			detail = 0xEE;
			CHECK(caseback_decode_config(m, sizeof(m), &cfg, &detail) == CASEBACK_ERR_INVALID_FIELD);
			CHECK(detail == bad[i].offset);
		}
		memcpy(p, pl, sizeof(pl));
		p[12] = 0x2D; /* burst_len 301 > 300 */
		p[13] = 0x01;
		CHECK(caseback_decode_config(p, 26, &cfg, &detail) == CASEBACK_ERR_INVALID_FIELD && detail == 12);
		CHECK(caseback_decode_config(pl, 25, &cfg, &detail) == CASEBACK_ERR_BAD_PAYLOAD_LENGTH);
	}

	/* BATTERY */
	struct caseback_battery bat_want = {4013, 1, 87, {210, 854, 6699, 15758}};
	struct caseback_battery bat;

	fr = load_frame(dir, "battery.bin");
	CHECK(caseback_decode_battery_frame(&fr, &bat, &detail) == CASEBACK_OK);
	CHECK(bat.voltage_mv == 4013 && bat.charging == 1 && bat.percent == 87);
	CHECK(bat.avg_current_ua[0] == 210 && bat.avg_current_ua[1] == 854);
	CHECK(bat.avg_current_ua[2] == 6699 && bat.avg_current_ua[3] == 15758);
	CHECK(caseback_encode_battery(&bat_want, p, sizeof(p), &len) == CASEBACK_OK && len == 12);
	check_file_and_encode(dir, "battery.bin", CASEBACK_MSG_BATTERY, p, len, NULL, 0);
	fr = load_frame(dir, "battery_query.bin");
	CHECK(fr.msg_type == CASEBACK_MSG_BATTERY && fr.payload_len == 0);
	bat_want.charging = 4;
	CHECK(caseback_encode_battery(&bat_want, p, sizeof(p), &len) == CASEBACK_ERR_INVALID_FIELD);
	bat_want.charging = 1;
	bat_want.percent = 101;
	CHECK(caseback_encode_battery(&bat_want, p, sizeof(p), &len) == CASEBACK_ERR_INVALID_FIELD);

	/* framing-only fixtures */
	fr = load_frame(dir, "max_payload.bin");
	CHECK(fr.payload_len == CASEBACK_MAX_PAYLOAD && fr.payload[0] == 0x80 && fr.payload[1] == ((37 + 0x80) & 0xFF));
	fr = load_frame(dir, "a5_payload.bin");
	CHECK(fr.payload_len == 21 && fr.payload[0] == 0xA5 && fr.payload[8] == 0xA5);
}

static void test_encode_bounds(void)
{
	uint8_t small[4], big[CASEBACK_MAX_FRAME + 8], pl[CASEBACK_MAX_PAYLOAD + 1];
	size_t out_len = 0;

	memset(pl, 0x5A, sizeof(pl));
	CHECK(caseback_encode_frame(0x01, NULL, 0, small, sizeof(small), &out_len) == CASEBACK_ERR_BUFFER_TOO_SMALL);
	CHECK(caseback_encode_frame(0x01, NULL, 1, big, sizeof(big), &out_len) == CASEBACK_ERR_NULL_ARGUMENT);
	CHECK(caseback_encode_frame(0x01, NULL, 0, NULL, 0, &out_len) == CASEBACK_ERR_NULL_ARGUMENT);
	CHECK(caseback_encode_frame(0x01, NULL, 0, big, sizeof(big), NULL) == CASEBACK_ERR_NULL_ARGUMENT);
	CHECK(caseback_encode_frame(0x10, pl, CASEBACK_MAX_PAYLOAD + 1, big, sizeof(big), &out_len) ==
	      CASEBACK_ERR_PAYLOAD_TOO_LONG);
	CHECK(caseback_encode_frame(0x10, pl, 512, big, sizeof(big), &out_len) == CASEBACK_ERR_PAYLOAD_TOO_LONG);
	CHECK(caseback_encode_frame(0x10, pl, CASEBACK_MAX_PAYLOAD, big, sizeof(big), &out_len) == CASEBACK_OK);
	CHECK(out_len == CASEBACK_MAX_FRAME);
	/* exact-fit and one-short buffers */
	CHECK(caseback_encode_frame(0x10, pl, CASEBACK_MAX_PAYLOAD, big, CASEBACK_MAX_FRAME, &out_len) == CASEBACK_OK);
	CHECK(caseback_encode_frame(0x10, pl, CASEBACK_MAX_PAYLOAD, big, CASEBACK_MAX_FRAME - 1, &out_len) ==
	      CASEBACK_ERR_BUFFER_TOO_SMALL);
}

static void test_decode_edges(void)
{
	struct caseback_frame fr;
	uint8_t ok[16], out[16];
	size_t n = 0;

	CHECK(caseback_encode_frame(0x01, NULL, 0, ok, sizeof(ok), &n) == CASEBACK_OK);
	CHECK(caseback_decode_frame(NULL, 0, &fr) == CASEBACK_ERR_TRUNCATED);
	CHECK(caseback_decode_frame(NULL, 5, &fr) == CASEBACK_ERR_NULL_ARGUMENT);
	CHECK(caseback_decode_frame(ok, n, NULL) == CASEBACK_ERR_NULL_ARGUMENT);
	CHECK(caseback_decode_frame(ok, 1, &fr) == CASEBACK_ERR_TRUNCATED);
	CHECK(caseback_decode_frame(ok, 2, &fr) == CASEBACK_ERR_TRUNCATED);
	CHECK(caseback_decode_frame(ok, 4, &fr) == CASEBACK_ERR_TRUNCATED);
	CHECK(caseback_decode_frame(ok, n - 1, &fr) == CASEBACK_ERR_TRUNCATED);
	memcpy(out, ok, n);
	out[1] = 2;
	CHECK(caseback_decode_frame(out, n, &fr) == CASEBACK_ERR_UNSUPPORTED_VERSION);
	out[0] = 0;
	CHECK(caseback_decode_frame(out, n, &fr) == CASEBACK_ERR_BAD_MAGIC);
	memcpy(out, ok, n);
	out[3] = 0xB0; /* payload_len 176 with only a header present */
	CHECK(caseback_decode_frame(out, n, &fr) == CASEBACK_ERR_PAYLOAD_TOO_LONG);
	memcpy(out, ok, n);
	out[n] = 0;
	CHECK(caseback_decode_frame(out, n + 1, &fr) == CASEBACK_ERR_LENGTH_MISMATCH);
}

int main(int argc, char **argv)
{
	const char *dir = argc > 1 ? argv[1] : "../../caseback-protocol/fixtures/golden";

	test_crc_check_value();
	test_limits_and_codes();
	test_manifest(dir);
	test_messages(dir);
	test_encode_bounds();
	test_decode_edges();
	printf("%d checks, %d failures\n", checks, failures);
	puts(failures ? "FAILED" : "ok");
	return failures ? 1 : 0;
}
