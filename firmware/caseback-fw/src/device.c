#include "device.h"

#include <string.h>

size_t caseback_device_id_normalize(uint8_t out[CASEBACK_DEVICE_ID_LEN], const uint8_t *raw,
				 int raw_len)
{
	size_t n = 0;

	memset(out, 0, CASEBACK_DEVICE_ID_LEN);
	if (raw != NULL && raw_len > 0) {
		n = (size_t)raw_len < CASEBACK_DEVICE_ID_LEN ? (size_t)raw_len
							  : CASEBACK_DEVICE_ID_LEN;
		memcpy(out, raw, n);
	}
	return n;
}

int caseback_build_name(char *out, size_t cap, const uint8_t id[CASEBACK_DEVICE_ID_LEN])
{
	static const char hex[] = "0123456789ABCDEF";
	const size_t prefix = sizeof(CASEBACK_NAME_PREFIX) - 1u;

	if (out == NULL || id == NULL || cap < CASEBACK_NAME_MAX) {
		return -1;
	}
	memcpy(out, CASEBACK_NAME_PREFIX, prefix);
	out[prefix + 0] = hex[id[CASEBACK_DEVICE_ID_LEN - 2] >> 4];
	out[prefix + 1] = hex[id[CASEBACK_DEVICE_ID_LEN - 2] & 0x0F];
	out[prefix + 2] = hex[id[CASEBACK_DEVICE_ID_LEN - 1] >> 4];
	out[prefix + 3] = hex[id[CASEBACK_DEVICE_ID_LEN - 1] & 0x0F];
	out[prefix + 4] = '\0';
	return (int)(prefix + CASEBACK_NAME_SUFFIX_HEX);
}

uint32_t caseback_capabilities(uint32_t implemented, bool encrypted_only)
{
	uint32_t caps = implemented & CASEBACK_CAP_KNOWN_MASK;

	if (encrypted_only) {
		caps |= CASEBACK_CAP_ENCRYPTED_ONLY;
	}
	return caps;
}

int caseback_build_info_frame(uint8_t *out, size_t out_cap, size_t *out_len,
			   const struct caseback_info *info)
{
	struct caseback_info masked;
	uint8_t payload[CASEBACK_INFO_PAYLOAD_LEN];
	size_t payload_len = 0;
	int rc;

	if (info == NULL) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	masked = *info;
	masked.capabilities &= CASEBACK_CAP_KNOWN_MASK;
	rc = caseback_encode_info(&masked, payload, sizeof(payload), &payload_len);
	if (rc != CASEBACK_OK) {
		return rc;
	}
	return caseback_encode_frame(CASEBACK_MSG_INFO_RESPONSE, payload, (uint16_t)payload_len, out,
				  out_cap, out_len);
}

static int build_error_frame(uint16_t code, uint8_t msg_type, uint8_t detail, uint8_t *out,
			     size_t out_cap, size_t *out_len)
{
	const struct caseback_error_msg err = {.code = code, .msg_type = msg_type, .detail = detail};
	uint8_t payload[CASEBACK_ERROR_PAYLOAD_LEN];
	size_t payload_len = 0;
	int rc = caseback_encode_error(&err, payload, sizeof(payload), &payload_len);

	if (rc != CASEBACK_OK) {
		return rc;
	}
	return caseback_encode_frame(CASEBACK_MSG_ERROR, payload, (uint16_t)payload_len, out, out_cap,
				  out_len);
}

/* Same value as the header field, or 0 when the header cannot be trusted. */
static uint8_t readable_msg_type(const uint8_t *in, size_t in_len)
{
	if (in != NULL && in_len >= 3 && in[0] == CASEBACK_MAGIC) {
		return in[2];
	}
	return 0;
}

int caseback_handle_control(const struct caseback_info *info, const uint8_t *in, size_t in_len,
			 uint8_t *out, size_t out_cap, size_t *out_len)
{
	struct caseback_frame frame;
	int rc;

	if (info == NULL || out == NULL || out_len == NULL) {
		return CASEBACK_ERR_NULL_ARGUMENT;
	}
	rc = caseback_decode_frame(in, in_len, &frame);
	if (rc != CASEBACK_OK) {
		return build_error_frame((uint16_t)rc, readable_msg_type(in, in_len), 0, out,
					 out_cap, out_len);
	}

	switch (frame.msg_type) {
	case CASEBACK_MSG_INFO_REQUEST:
		if (frame.payload_len != 0) {
			return build_error_frame(CASEBACK_ERR_BAD_PAYLOAD_LENGTH, frame.msg_type, 0,
						 out, out_cap, out_len);
		}
		return caseback_build_info_frame(out, out_cap, out_len, info);
	/* device-to-phone messages sent by the phone */
	case CASEBACK_MSG_INFO_RESPONSE:
	case CASEBACK_MSG_ERROR:
	case CASEBACK_MSG_STREAM_DATA:
	case CASEBACK_MSG_CONFIG_STATE:
	case CASEBACK_MSG_BATTERY:
		return build_error_frame(CASEBACK_ERR_WRONG_DIRECTION, frame.msg_type, 0, out,
					 out_cap, out_len);
	/* defined requests this build does not implement yet */
	case CASEBACK_MSG_TIME_ANCHOR:
	case CASEBACK_MSG_STREAM_CONTROL:
	case CASEBACK_MSG_HISTORY_QUERY:
	case CASEBACK_MSG_HISTORY_ACK:
	case CASEBACK_MSG_CONFIG_SET:
		return build_error_frame(CASEBACK_ERR_UNSUPPORTED, frame.msg_type, 0, out, out_cap,
					 out_len);
	default:
		return build_error_frame(CASEBACK_ERR_UNKNOWN_MSG_TYPE, frame.msg_type, 0, out,
					 out_cap, out_len);
	}
}

void caseback_afe_build_read(uint8_t reg, uint8_t tx[CASEBACK_AFE_SPI_FRAME_LEN])
{
	tx[0] = reg;
	tx[1] = CASEBACK_AFE_SPI_CMD_READ;
	tx[2] = 0x00;
}

const char *caseback_afe_part_name(uint8_t part_id)
{
	switch (part_id) {
	case CASEBACK_AFE_PART_ID_MAX86140:
		return "MAX86140";
	case CASEBACK_AFE_PART_ID_MAX86141:
		return "MAX86141";
	default:
		return NULL;
	}
}
