#include "factory.h"
#include "protocol.h"
#include <errno.h>
#include <string.h>

void factory_set(struct factory_record *r, enum factory_stage stage, const uint8_t *digest)
{
	memset(r, 0, sizeof(*r));
	r->stage = stage;
	if (digest)
		memcpy(r->digest, digest, sizeof(r->digest));
	r->crc = caseback_crc16_ccitt((const uint8_t *)r, offsetof(struct factory_record, crc));
}

bool factory_armable(const struct factory_record *r, bool docked, bool linked, bool bonded)
{
	return docked && !linked && !bonded && (r->stage == FACTORY_NEW || r->stage == FACTORY_ARMED);
}

bool factory_matches(const struct factory_record *r, const uint8_t *digest, bool docked, bool bonded)
{
	uint8_t difference = 0;
	for (unsigned i = 0; i < FACTORY_DIGEST_SIZE; ++i)
		difference |= r->digest[i] ^ digest[i];
	return r->stage == FACTORY_ARMED && docked && bonded && difference == 0;
}

/* Erase the data partition while PENDING survives in settings. Then erase the
 * entire settings partition while WIPE_SETTINGS survives in the clean journal.
 * No radio or sensor/history worker is started during this transaction. */
int factory_recover(const struct factory_ops *ops, struct factory_record *r)
{
	uint32_t mark = 0;
	int mark_rc = ops->mark_read(&mark);
	if (!mark_rc && mark == FACTORY_SEALED) {
		factory_set(r, FACTORY_DONE, NULL);
		return FACTORY_READY;
	}
	if (!mark_rc && mark != FACTORY_WIPE_SETTINGS)
		return -EINVAL;
	if (mark_rc) {
		int rc = ops->state_read(r);
		if (rc == -ENOENT) {
			if (mark_rc != -ENOENT)
				return -EIO;
			factory_set(r, FACTORY_NEW, NULL);
			return FACTORY_READY;
		}
		if (rc || r->crc != caseback_crc16_ccitt((const uint8_t *)r, offsetof(struct factory_record, crc)))
			return -EIO;
		if (r->stage == FACTORY_ARMED)
			return mark_rc == -ENOENT ? FACTORY_READY : -EIO;
		if (r->stage != FACTORY_PENDING)
			return -EINVAL;
		if (ops->history_erase() || ops->mark_save(FACTORY_WIPE_SETTINGS))
			return -EIO;
	}
	if (ops->settings_erase() || ops->mark_save(FACTORY_SEALED))
		return -EIO;
	factory_set(r, FACTORY_DONE, NULL);
	return FACTORY_RETIRED;
}

bool factory_should_sleep(bool optical_lab, unsigned bonds, int dock)
{
	return !optical_lab && !bonds && dock != 1;
}
