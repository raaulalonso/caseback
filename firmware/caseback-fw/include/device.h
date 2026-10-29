#pragma once

/* Zephyr-free device logic: advertised name, device id, capability mask,
 * CONTROL-frame dispatch, AFE probe frame. Host-testable (tests/test_device.c);
 * main.c only supplies the raw inputs.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "protocol.h"

/* Advertised name = prefix + last two device_id bytes as upper-case hex. */
#define CASEBACK_NAME_PREFIX "Caseback-"
#define CASEBACK_NAME_SUFFIX_HEX 4u
#define CASEBACK_NAME_MAX (sizeof(CASEBACK_NAME_PREFIX) - 1u + CASEBACK_NAME_SUFFIX_HEX + 1u)

/* Bits 0..7 are defined by the spec (protocol.h); 8..31 are reserved. */
#define CASEBACK_CAP_KNOWN_MASK 0xFFu

/* What this firmware build really implements. INFO/CONTROL/DATA only, no
 * streams, log or DFU yet; raise it together with the feature, never before.
 * ENCRYPTED_ONLY is not listed here: it follows the Kconfig option.
 */
#define CASEBACK_IMPLEMENTED_CAPS CASEBACK_CAP_NONE

/* Copy up to CASEBACK_DEVICE_ID_LEN bytes of `raw` (raw_len <= 0 or NULL: none)
 * into `out`, zero-padding the rest.
 * Returns the number of raw bytes used.
 */
size_t caseback_device_id_normalize(uint8_t out[CASEBACK_DEVICE_ID_LEN], const uint8_t *raw,
				 int raw_len);

/* Writes "Caseback-XXXX" and a NUL. Returns the name length, or -1 if
 * `cap` < CASEBACK_NAME_MAX or an argument is NULL.
 */
int caseback_build_name(char *out, size_t cap, const uint8_t id[CASEBACK_DEVICE_ID_LEN]);

/* `implemented` restricted to the spec-defined bits, plus ENCRYPTED_ONLY when
 * every characteristic requires an encrypted link.
 */
uint32_t caseback_capabilities(uint32_t implemented, bool encrypted_only);

/* Complete INFO_RESPONSE frame for `info` (capabilities are masked to the
 * known bits). Returns CASEBACK_OK or an enum caseback_error from the encoder.
 */
int caseback_build_info_frame(uint8_t *out, size_t out_cap, size_t *out_len,
			   const struct caseback_info *info);

/* One write on CONTROL -> one frame to notify on DATA.
 * `in`/`in_len` are the raw ATT value. The reply is INFO_RESPONSE for
 * INFO_REQUEST and an ERROR frame for anything undecodable, unsupported or
 * not phone-to-device (msg_type 0 in the ERROR when the header is unreadable).
 * `out_cap` should be CASEBACK_MAX_FRAME. Returns CASEBACK_OK with the reply in
 * `out`/`out_len`, or the encoder error (nothing to send).
 */
int caseback_handle_control(const struct caseback_info *info, const uint8_t *in, size_t in_len,
			 uint8_t *out, size_t out_cap, size_t *out_len);

/* MAX86140/MAX86141 PPG AFE, SPI only (datasheet "MAX86140/MAX86141", Maxim/Analog Devices).
 * Register read = 3-byte frame under one CSB low: {address, command, dummy}; the
 * data byte is clocked out during the third byte. PART_ID (0xFF) reads 0x24 on
 * the MAX86140 and 0x25 on the MAX86141.
 * The command byte for a read (R/W flag = bit 7 of the second byte) could not
 * be confirmed from the text of the datasheet (the figure labels are lost in
 * the extract), so 0x80 is the usual Maxim convention, not a verified value.
 */
#define CASEBACK_AFE_REG_PART_ID 0xFFu
#define CASEBACK_AFE_SPI_CMD_READ 0x80u
#define CASEBACK_AFE_SPI_FRAME_LEN 3u
#define CASEBACK_AFE_PART_ID_MAX86140 0x24u
#define CASEBACK_AFE_PART_ID_MAX86141 0x25u

void caseback_afe_build_read(uint8_t reg, uint8_t tx[CASEBACK_AFE_SPI_FRAME_LEN]);

/* "MAX86140" / "MAX86141", or NULL for any other value. */
const char *caseback_afe_part_name(uint8_t part_id);
