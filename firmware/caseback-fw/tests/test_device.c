/* Host-side test for src/device.c (no Zephyr).
 *
 * Build & run (from firmware/caseback-fw):
 *   cc -Wall -Wextra -Werror -Iinclude -o /tmp/test_device tests/test_device.c src/device.c src/protocol.c
 *   /tmp/test_device
 */
#include <stdio.h>
#include <string.h>

#include "device.h"

static int failures;

#define CHECK(cond)                                                            \
	do {                                                                   \
		if (!(cond)) {                                                 \
			printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
			failures++;                                            \
		}                                                              \
	} while (0)

static const uint8_t ID[CASEBACK_DEVICE_ID_LEN] = {0x01, 0x23, 0x45, 0x67,
						0x89, 0xAB, 0xA1, 0xB2};

static void test_normalize(void)
{
	uint8_t out[CASEBACK_DEVICE_ID_LEN];
	const uint8_t shortid[3] = {0xAA, 0xBB, 0xCC};
	uint8_t longid[12];

	for (size_t i = 0; i < sizeof(longid); i++) {
		longid[i] = (uint8_t)(i + 1);
	}

	CHECK(caseback_device_id_normalize(out, ID, 8) == 8);
	CHECK(memcmp(out, ID, sizeof(ID)) == 0);

	memset(out, 0xEE, sizeof(out));
	CHECK(caseback_device_id_normalize(out, shortid, 3) == 3);
	CHECK(out[0] == 0xAA && out[2] == 0xCC && out[3] == 0 && out[7] == 0);

	CHECK(caseback_device_id_normalize(out, longid, (int)sizeof(longid)) == 8);
	CHECK(out[7] == 8);

	memset(out, 0xEE, sizeof(out));
	CHECK(caseback_device_id_normalize(out, ID, -5) == 0);
	CHECK(out[0] == 0 && out[7] == 0);
	memset(out, 0xEE, sizeof(out));
	CHECK(caseback_device_id_normalize(out, NULL, 8) == 0);
	CHECK(out[0] == 0);
}

static void test_name(void)
{
	char name[CASEBACK_NAME_MAX];
	char tiny[CASEBACK_NAME_MAX - 1];
	const uint8_t zero[CASEBACK_DEVICE_ID_LEN] = {0};

	CHECK(CASEBACK_NAME_MAX == 14);
	CHECK(caseback_build_name(name, sizeof(name), ID) == 13);
	CHECK(strcmp(name, "Caseback-A1B2") == 0);

	CHECK(caseback_build_name(name, sizeof(name), zero) == 13);
	CHECK(strcmp(name, "Caseback-0000") == 0);

	CHECK(caseback_build_name(tiny, sizeof(tiny), ID) == -1);
	CHECK(caseback_build_name(NULL, sizeof(name), ID) == -1);
	CHECK(caseback_build_name(name, sizeof(name), NULL) == -1);
	/* scan response: length + type + name must fit 31 bytes */
	CHECK(2u + CASEBACK_NAME_MAX - 1u <= 31u);
}

static void test_capabilities(void)
{
	CHECK(CASEBACK_CAP_KNOWN_MASK == 0xFFu);
	CHECK(CASEBACK_IMPLEMENTED_CAPS == CASEBACK_CAP_NONE);
	CHECK(caseback_capabilities(CASEBACK_IMPLEMENTED_CAPS, false) == 0);
	CHECK(caseback_capabilities(CASEBACK_IMPLEMENTED_CAPS, true) == CASEBACK_CAP_ENCRYPTED_ONLY);
	CHECK(caseback_capabilities(0xFFFFFFFFu, false) == 0xFFu);
	CHECK(caseback_capabilities(CASEBACK_CAP_PPG_RAW | CASEBACK_CAP_DFU_SMP, false) == 0x21u);
	CHECK(caseback_capabilities(CASEBACK_CAP_IBI_LOG, true) == 0xC0u);
	CHECK(caseback_capabilities(0x100u, false) == 0);
}

static struct caseback_info make_info(uint32_t caps)
{
	struct caseback_info info;

	memcpy(info.device_id, ID, sizeof(ID));
	info.hw_rev = 0x0102;
	info.fw_rev = 0x0304;
	info.capabilities = caps;
	return info;
}

static void test_info(void)
{
	static const uint8_t expect_payload[CASEBACK_INFO_PAYLOAD_LEN] = {
		0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xA1, 0xB2,
		0x02, 0x01, /* hw_rev 0x0102 */
		0x04, 0x03, /* fw_rev 0x0304 */
		0x05, 0x00, 0x00, 0x00, /* PPG raw + ACCEL */
	};
	uint8_t frame[CASEBACK_MAX_FRAME];
	size_t frame_len = 0;
	struct caseback_frame decoded;
	struct caseback_info info = make_info(CASEBACK_CAP_PPG_RAW | CASEBACK_CAP_ACCEL);

	CHECK(caseback_build_info_frame(frame, sizeof(frame), &frame_len, &info) == CASEBACK_OK);
	CHECK(frame_len == CASEBACK_HEADER_LEN + CASEBACK_INFO_PAYLOAD_LEN + CASEBACK_CRC_LEN);
	CHECK(caseback_decode_frame(frame, frame_len, &decoded) == CASEBACK_OK);
	CHECK(decoded.msg_type == CASEBACK_MSG_INFO_RESPONSE);
	CHECK(decoded.payload_len == CASEBACK_INFO_PAYLOAD_LEN);
	CHECK(memcmp(decoded.payload, expect_payload, sizeof(expect_payload)) == 0);

	/* reserved capability bits never reach the wire */
	info.capabilities = 0xFFFFFFFFu;
	CHECK(caseback_build_info_frame(frame, sizeof(frame), &frame_len, &info) == CASEBACK_OK);
	CHECK(caseback_decode_frame(frame, frame_len, &decoded) == CASEBACK_OK);
	CHECK(decoded.payload[12] == 0xFF && decoded.payload[13] == 0 && decoded.payload[15] == 0);

	CHECK(caseback_build_info_frame(frame, 10, &frame_len, &info) == CASEBACK_ERR_BUFFER_TOO_SMALL);
	CHECK(caseback_build_info_frame(frame, sizeof(frame), &frame_len, NULL) ==
	      CASEBACK_ERR_NULL_ARGUMENT);
}

/* Decode a reply and check it is an ERROR frame with the given fields. */
static void check_error(const uint8_t *reply, size_t reply_len, uint16_t code, uint8_t msg_type,
			int line)
{
	struct caseback_frame f;
	struct caseback_error_msg e;

	if (caseback_decode_frame(reply, reply_len, &f) != CASEBACK_OK ||
	    caseback_decode_error_frame(&f, &e) != CASEBACK_OK || e.code != code ||
	    e.msg_type != msg_type || e.detail != 0) {
		printf("FAIL line %d: expected ERROR code 0x%04x type 0x%02x\n", line, code, msg_type);
		failures++;
	}
}

static size_t make_frame(uint8_t *out, uint8_t type, const uint8_t *payload, uint16_t plen)
{
	size_t n = 0;

	CHECK(caseback_encode_frame(type, payload, plen, out, CASEBACK_MAX_FRAME, &n) == CASEBACK_OK);
	return n;
}

static void test_control(void)
{
	const struct caseback_info info = make_info(CASEBACK_CAP_ENCRYPTED_ONLY);
	uint8_t in[CASEBACK_MAX_FRAME + 16];
	uint8_t out[CASEBACK_MAX_FRAME];
	size_t in_len, out_len = 0;
	struct caseback_frame f;
	struct caseback_info got;
	static const uint8_t junk[3] = {1, 2, 3};
	uint8_t big[CASEBACK_MAX_PAYLOAD];

	memset(big, 0x5A, sizeof(big));

	/* INFO_REQUEST -> INFO_RESPONSE, same bytes as reading INFO */
	in_len = make_frame(in, CASEBACK_MSG_INFO_REQUEST, NULL, 0);
	CHECK(caseback_handle_control(&info, in, in_len, out, sizeof(out), &out_len) == CASEBACK_OK);
	CHECK(caseback_decode_frame(out, out_len, &f) == CASEBACK_OK);
	CHECK(caseback_decode_info_frame(&f, &got) == CASEBACK_OK);
	CHECK(memcmp(got.device_id, ID, sizeof(ID)) == 0);
	CHECK(got.hw_rev == 0x0102 && got.fw_rev == 0x0304);
	CHECK(got.capabilities == CASEBACK_CAP_ENCRYPTED_ONLY);
	{
		uint8_t ref[CASEBACK_MAX_FRAME];
		size_t ref_len = 0;

		CHECK(caseback_build_info_frame(ref, sizeof(ref), &ref_len, &info) == CASEBACK_OK);
		CHECK(ref_len == out_len && memcmp(ref, out, out_len) == 0);
	}

	/* INFO_REQUEST with a payload */
	in_len = make_frame(in, CASEBACK_MSG_INFO_REQUEST, junk, sizeof(junk));
	CHECK(caseback_handle_control(&info, in, in_len, out, sizeof(out), &out_len) == CASEBACK_OK);
	CHECK(caseback_decode_frame(out, out_len, &f) == CASEBACK_OK);
	{
		struct caseback_error_msg e;

		CHECK(caseback_decode_error_frame(&f, &e) == CASEBACK_OK);
		CHECK(e.code == CASEBACK_ERR_BAD_PAYLOAD_LENGTH && e.msg_type == 0x01 &&
		      e.detail == 0);
	}

	/* bad CRC */
	in_len = make_frame(in, CASEBACK_MSG_INFO_REQUEST, NULL, 0);
	in[in_len - 1] ^= 0xFF;
	CHECK(caseback_handle_control(&info, in, in_len, out, sizeof(out), &out_len) == CASEBACK_OK);
	check_error(out, out_len, CASEBACK_ERR_BAD_CRC, 0x01, __LINE__);

	/* unsupported proto_ver (the CRC is not reached) */
	in_len = make_frame(in, CASEBACK_MSG_INFO_REQUEST, NULL, 0);
	in[1] = 0x02;
	CHECK(caseback_handle_control(&info, in, in_len, out, sizeof(out), &out_len) == CASEBACK_OK);
	check_error(out, out_len, CASEBACK_ERR_UNSUPPORTED_VERSION, 0x01, __LINE__);

	/* unknown and reserved msg_type */
	in_len = make_frame(in, 0x7E, NULL, 0);
	CHECK(caseback_handle_control(&info, in, in_len, out, sizeof(out), &out_len) == CASEBACK_OK);
	check_error(out, out_len, CASEBACK_ERR_UNKNOWN_MSG_TYPE, 0x7E, __LINE__);
	in_len = make_frame(in, CASEBACK_MSG_DFU_RESERVED_FIRST, NULL, 0);
	CHECK(caseback_handle_control(&info, in, in_len, out, sizeof(out), &out_len) == CASEBACK_OK);
	check_error(out, out_len, CASEBACK_ERR_UNKNOWN_MSG_TYPE, CASEBACK_MSG_DFU_RESERVED_FIRST,
		    __LINE__);

	/* defined but not implemented, and wrong direction */
	in_len = make_frame(in, CASEBACK_MSG_STREAM_CONTROL, NULL, 0);
	CHECK(caseback_handle_control(&info, in, in_len, out, sizeof(out), &out_len) == CASEBACK_OK);
	check_error(out, out_len, CASEBACK_ERR_UNSUPPORTED, CASEBACK_MSG_STREAM_CONTROL, __LINE__);
	in_len = make_frame(in, CASEBACK_MSG_BATTERY, NULL, 0);
	CHECK(caseback_handle_control(&info, in, in_len, out, sizeof(out), &out_len) == CASEBACK_OK);
	check_error(out, out_len, CASEBACK_ERR_WRONG_DIRECTION, CASEBACK_MSG_BATTERY, __LINE__);

	/* oversize: declared payload above the maximum, and a valid frame with trailing bytes */
	in_len = make_frame(in, CASEBACK_MSG_CONFIG_SET, big, sizeof(big));
	CHECK(in_len == CASEBACK_MAX_FRAME);
	in[3] = (uint8_t)((CASEBACK_MAX_PAYLOAD + 1) & 0xFF);
	in[4] = (uint8_t)((CASEBACK_MAX_PAYLOAD + 1) >> 8);
	CHECK(caseback_handle_control(&info, in, in_len, out, sizeof(out), &out_len) == CASEBACK_OK);
	check_error(out, out_len, CASEBACK_ERR_PAYLOAD_TOO_LONG, CASEBACK_MSG_CONFIG_SET, __LINE__);
	in_len = make_frame(in, CASEBACK_MSG_INFO_REQUEST, NULL, 0);
	memset(&in[in_len], 0, 9);
	CHECK(caseback_handle_control(&info, in, in_len + 9, out, sizeof(out), &out_len) == CASEBACK_OK);
	check_error(out, out_len, CASEBACK_ERR_LENGTH_MISMATCH, 0x01, __LINE__);

	/* unreadable header: msg_type 0 */
	in[0] = 0x00;
	CHECK(caseback_handle_control(&info, in, 4, out, sizeof(out), &out_len) == CASEBACK_OK);
	check_error(out, out_len, CASEBACK_ERR_BAD_MAGIC, 0x00, __LINE__);
	CHECK(caseback_handle_control(&info, in, 0, out, sizeof(out), &out_len) == CASEBACK_OK);
	check_error(out, out_len, CASEBACK_ERR_TRUNCATED, 0x00, __LINE__);

	/* arguments */
	CHECK(caseback_handle_control(NULL, in, 1, out, sizeof(out), &out_len) ==
	      CASEBACK_ERR_NULL_ARGUMENT);
	CHECK(caseback_handle_control(&info, in, 1, out, 4, &out_len) == CASEBACK_ERR_BUFFER_TOO_SMALL);
}

static void test_afe(void)
{
	uint8_t tx[CASEBACK_AFE_SPI_FRAME_LEN];

	caseback_afe_build_read(CASEBACK_AFE_REG_PART_ID, tx);
	CHECK(tx[0] == 0xFF && tx[1] == CASEBACK_AFE_SPI_CMD_READ && tx[2] == 0x00);
	CHECK(strcmp(caseback_afe_part_name(0x24), "MAX86140") == 0);
	CHECK(strcmp(caseback_afe_part_name(0x25), "MAX86141") == 0);
	CHECK(caseback_afe_part_name(0x00) == NULL);
	CHECK(caseback_afe_part_name(0xFF) == NULL);
}

int main(void)
{
	test_normalize();
	test_name();
	test_capabilities();
	test_info();
	test_control();
	test_afe();
	if (failures) {
		printf("%d failure(s)\n", failures);
		return 1;
	}
	printf("test_device: ok\n");
	return 0;
}
