#include "history.h"
#include "protocol.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__, "NVS schema uses little endian");
_Static_assert(HISTORY_MAX_BYTES == 116, "unexpected page layout");
_Static_assert(sizeof(struct history_ack) == 6, "unexpected ACK layout");

static uint16_t checksum(const void *bytes, size_t size)
{
	return caseback_crc16_ccitt(bytes, size - sizeof(uint16_t));
}

int history_load(struct history_log *log, unsigned key, const void *data, size_t size)
{
	if (key == HISTORY_ACK_KEY) {
		struct history_ack ack;
		if (size != sizeof(ack))
			return -EINVAL;
		memcpy(&ack, data, size);
		if (ack.crc != checksum(&ack, size))
			return -EINVAL;
		log->acknowledged = ack.cursor;
		return 0;
	}
	const size_t header = offsetof(struct history_page, activity);
	if (key >= HISTORY_SLOTS || size <= header + 2 || size > HISTORY_MAX_BYTES)
		return -EINVAL;
	struct history_page p = {0};
	uint16_t crc;
	memcpy(&p, data, size - sizeof(crc));
	memcpy(&crc, (const uint8_t *)data + size - sizeof(crc), sizeof(crc));
	if (crc != checksum(data, size) || p.version != 1 || !p.count ||
	    size != header + p.count + sizeof(crc) ||
	    p.count > EPOCHS_PER_PAGE || p.first > UINT32_MAX - p.count)
		return -EINVAL;
	for (unsigned i = 0; i < p.count; ++i)
		if ((p.activity[i] & 0x7f) > 30)
			return -EINVAL;
	log->pages[key] = p;
	return 0;
}

int history_recover(struct history_log *log)
{
	unsigned populated = 0;
	for (unsigned i = 0; i < HISTORY_SLOTS; ++i) {
		const struct history_page *p = &log->pages[i];
		if (!p->count)
			continue;
		if (!populated || p->first < log->oldest)
			log->oldest = p->first;
		if (p->first + p->count > log->next) {
			log->next = p->first + p->count;
			log->newest = i;
		}
		++populated;
	}
	/* Consecutive valid NVS slots must cover an unbroken sequence of cursors. */
	uint32_t end = log->next;
	unsigned i = log->newest;
	for (unsigned n = 0; n < populated; ++n) {
		const struct history_page *p = &log->pages[i];
		if (!p->count || p->first + p->count != end)
			return -EINVAL;
		end = p->first;
		i = (i + HISTORY_SLOTS - 1) % HISTORY_SLOTS;
	}
	return end == log->oldest && log->acknowledged <= log->next ? 0 : -EINVAL;
}

static size_t page_bytes(const struct history_page *p, uint8_t *bytes)
{
	size_t prefix = offsetof(struct history_page, activity) + p->count;
	memcpy(bytes, p, prefix);
	uint16_t crc = caseback_crc16_ccitt(bytes, prefix);
	memcpy(bytes + prefix, &crc, sizeof(crc));
	return prefix + sizeof(crc);
}

int history_append(struct history_log *log, uint32_t boot, uint64_t uptime,
		   unsigned activity, bool gap, history_write write)
{
	if (activity > 30 || log->next == UINT32_MAX)
		return -ERANGE;
	unsigned slot = log->newest;
	struct history_page p = log->pages[slot];
	bool contiguous = p.count && p.boot == boot &&
		p.uptime + (uint64_t)p.count * HISTORY_EPOCH_MS == uptime;
	if (!contiguous || p.count == EPOCHS_PER_PAGE) {
		slot = log->next ? (slot + 1) % HISTORY_SLOTS : 0;
		p = (struct history_page){.version = 1, .first = log->next, .boot = boot,
					  .uptime = uptime};
	}
	p.activity[p.count++] = (uint8_t)(activity | ((gap || !contiguous) ? 0x80 : 0));
	uint8_t bytes[HISTORY_MAX_BYTES];
	size_t size = page_bytes(&p, bytes);
	int rc = write(slot, bytes, size);
	if (rc)
		return rc;
	const struct history_page *previous = &log->pages[slot];
	if (previous->count && previous->first != p.first)
		log->oldest = previous->first + previous->count;
	log->pages[slot] = p;
	log->newest = slot;
	++log->next;
	return 0;
}

int history_acknowledge(struct history_log *log, uint32_t cursor, history_write write)
{
	if (cursor > log->next)
		return -ERANGE;
	if (cursor <= log->acknowledged)
		return 0;
	struct history_ack ack = {.cursor = cursor};
	ack.crc = checksum(&ack, sizeof(ack));
	int rc = write(HISTORY_ACK_KEY, &ack, sizeof(ack));
	if (!rc)
		log->acknowledged = cursor;
	return rc;
}

bool history_epoch(const struct history_log *log, uint32_t cursor, uint32_t *boot,
		   uint64_t *uptime, uint8_t *activity, bool *gap)
{
	if (cursor < log->oldest || cursor >= log->next)
		return false;
	for (unsigned i = 0; i < HISTORY_SLOTS; ++i) {
		const struct history_page *p = &log->pages[i];
		uint32_t index = cursor - p->first;
		if (index >= p->count)
			continue;
		*boot = p->boot;
		*uptime = p->uptime + (uint64_t)index * HISTORY_EPOCH_MS;
		*activity = p->activity[index] & 0x7f;
		*gap = (p->activity[index] & 0x80) != 0;
		return true;
	}
	return false;
}

bool activity_sample(struct activity_window *w, uint64_t second, const int16_t *axes)
{
	bool consecutive = w->previous && second == w->second + 1;
	if (!axes || !consecutive) {
		w->count = 0;
		w->changes = 0;
		w->gap = true;
		w->previous = false;
	}
	if (!axes)
		return false;
	if (second % 30 == 0) {
		w->count = 0;
		w->changes = 0;
	}
	if (consecutive) {
		unsigned delta = 0;
		for (unsigned i = 0; i < 3; ++i)
			delta += abs((int)axes[i] - w->axes[i]);
		w->changes += delta >= 1024;
	}
	memcpy(w->axes, axes, sizeof(w->axes));
	w->previous = true;
	w->second = second;
	++w->count;
	return second % 30 == 29 && w->count == 30;
}

uint32_t history_query(const struct history_log *log, uint32_t cursor, uint16_t limit,
		       uint32_t *first, uint8_t p[9])
{
	*first = cursor < log->oldest ? log->oldest : cursor;
	memcpy(p, first, 4);
	memcpy(p + 4, &log->next, 4);
	p[8] = log->oldest > cursor && log->oldest > log->acknowledged;
	return limit && log->next - *first > limit ? *first + limit : log->next;
}

bool history_payload(const struct history_log *log, uint32_t cursor, uint16_t seq,
		     uint8_t p[26])
{
	uint32_t boot;
	uint64_t uptime;
	bool gap;
	uint8_t activity;
	if (!history_epoch(log, cursor, &boot, &uptime, &activity, &gap))
		return false;
	memset(p, 0, 26);
	memcpy(p, &seq, 2);
	memcpy(p + 2, &boot, 4);
	memcpy(p + 6, &uptime, 8);
	p[14] = 3;
	p[15] = 2;
	p[16] = 1 | (gap ? 2 : 0);
	p[19] = 1;
	p[24] = activity;
	return true;
}

/* The legacy settings store is read-only throughout migration. The marker becomes
 * committed only after validating every new value and its read-back. */
int history_open(struct history_log *log, history_read read, history_write write,
		 int (*legacy)(struct history_log *))
{
	const uint32_t importing = 0x43424831, committed = 0x43424832;
	uint32_t marker = 0;
	int size = read(HISTORY_FORMAT_KEY, &marker, sizeof(marker));
	if (size != -ENOENT && (size != sizeof(marker) ||
	    (marker != importing && marker != committed)))
		return -EINVAL;
	memset(log, 0, sizeof(*log));
	uint8_t bytes[HISTORY_MAX_BYTES], check[HISTORY_MAX_BYTES];
	if (marker == committed) {
		for (unsigned key = 0; key <= HISTORY_ACK_KEY; ++key) {
			size = read(key, bytes, sizeof(bytes));
			if (size != -ENOENT && (size < 0 || (size_t)size > sizeof(bytes) ||
			    history_load(log, key, bytes, (size_t)size)))
				return -EIO;
		}
		return history_recover(log);
	}
	if (legacy(log) || history_recover(log))
		return -EINVAL;
	if (!marker && write(HISTORY_FORMAT_KEY, &importing, sizeof(importing)))
		return -EIO;
	for (unsigned key = 0; key <= HISTORY_ACK_KEY; ++key) {
		size_t expected = 0;
		if (key == HISTORY_ACK_KEY && log->acknowledged) {
			struct history_ack ack = {.cursor = log->acknowledged};
			ack.crc = checksum(&ack, sizeof(ack));
			memcpy(bytes, &ack, sizeof(ack));
			expected = sizeof(ack);
		} else if (key < HISTORY_SLOTS && log->pages[key].count) {
			expected = page_bytes(&log->pages[key], bytes);
		}
		if (expected && write(key, bytes, expected))
			return -EIO;
		size = read(key, check, sizeof(check));
		if (!expected) {
			if (size != -ENOENT)
				return -EINVAL;
		} else if (size != (int)expected || memcmp(bytes, check, expected)) {
			return -EIO;
		}
	}
	return write(HISTORY_FORMAT_KEY, &committed, sizeof(committed));
}
