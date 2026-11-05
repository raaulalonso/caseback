#include "history.h"
#include "protocol.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

static uint8_t media[HISTORY_SLOTS + 1][HISTORY_MAX_BYTES];
static size_t lengths[HISTORY_SLOTS + 1];
static bool write_failure;

static int store(unsigned slot, const void *data, size_t size)
{
	assert(slot <= HISTORY_ACK_KEY && size <= sizeof(media[slot]));
	if (write_failure)
		return -ENOSPC;
	memcpy(media[slot], data, size);
	lengths[slot] = size;
	return 0;
}

static int restore(struct history_log *log)
{
	memset(log, 0, sizeof(*log));
	for (unsigned i = 0; i <= HISTORY_ACK_KEY; ++i)
		if (lengths[i] && history_load(log, i, media[i], lengths[i]))
			return -EINVAL;
	return history_recover(log);
}

static void check_epoch(struct history_log *log, uint32_t cursor, uint32_t expected_boot,
			uint64_t expected_uptime, unsigned expected_activity, bool expected_gap)
{
	uint32_t boot;
	uint64_t uptime;
	uint8_t activity;
	bool gap;
	assert(history_epoch(log, cursor, &boot, &uptime, &activity, &gap));
	assert(boot == expected_boot && uptime == expected_uptime);
	assert(activity == expected_activity && gap == expected_gap);
}

static void activity_test(void)
{
	struct activity_window w = {0};
	const int16_t still[3] = {0, 0, 8192}, moved[3] = {0, 512, 8704};
	for (int sec = 0; sec < 60; ++sec) {
		assert(activity_sample(&w, sec, sec == 10 ? moved : still) == (sec % 30 == 29));
		if (sec == 29) {
			assert(w.changes == 2 && w.gap);
			w.gap = false;
		}
	}
	assert(w.changes == 0 && !w.gap);
	for (int sec = 60; sec < 120; ++sec)
		assert(activity_sample(&w, sec, sec == 77 ? NULL : still) == (sec == 119));
	assert(w.gap && w.changes == 0);
}

static uint8_t destination[HISTORY_FORMAT_KEY + 1][HISTORY_MAX_BYTES];
static size_t sizes[HISTORY_FORMAT_KEY + 1];
static unsigned attempts, cut_at;
static bool cut_after_commit;

static int new_read(unsigned key, void *bytes, size_t size)
{
	if (!sizes[key])
		return -ENOENT;
	assert(size >= sizes[key]);
	memcpy(bytes, destination[key], sizes[key]);
	return sizes[key];
}
static int new_write(unsigned key, const void *bytes, size_t size)
{
	bool cut = ++attempts == cut_at;
	if (cut && !cut_after_commit)
		return -EIO;
	memcpy(destination[key], bytes, size);
	sizes[key] = size;
	return cut ? -EIO : 0;
}
static int legacy_load(struct history_log *log)
{
	for (unsigned i = 0; i <= HISTORY_ACK_KEY; ++i)
		if (lengths[i] && history_load(log, i, media[i], lengths[i]))
			return -EINVAL;
	return 0;
}
static int no_legacy_reads(struct history_log *log)
{
	(void)log;
	assert(0 && "committed migration returned to the old region");
	return -EIO;
}

static void migration_test(void)
{
	struct history_log result;
	attempts = cut_at = 0;
	assert(history_open(&result, new_read, new_write, legacy_load) == 0);
	unsigned boundaries = attempts;
	for (unsigned order = 0; order < 2; ++order) {
		for (unsigned edge = 1; edge <= boundaries; ++edge) {
			memset(sizes, 0, sizeof(sizes));
			cut_at = edge;
			cut_after_commit = order != 0;
			attempts = 0;
			assert(history_open(&result, new_read, new_write, legacy_load) < 0);
			cut_at = 0;
			assert(history_open(&result, new_read, new_write, legacy_load) == 0);
			assert(result.oldest == 96 && result.next == 9640 && result.acknowledged == 2000);
			check_epoch(&result, 9639, 20, 1000 * 30000ULL, 7, false);
			assert(history_open(&result, new_read, new_write, no_legacy_reads) == 0);
		}
	}
	destination[HISTORY_FORMAT_KEY][0] ^= 0x08;
	assert(history_open(&result, new_read, new_write, no_legacy_reads) < 0);
	printf("Migration test: %u interruptions before/after durable writes, original history and ACK retained.\n",
	       2 * boundaries);
}

static void print_frame(uint8_t msg, const uint8_t *payload, size_t size)
{
	uint8_t wire[CASEBACK_MAX_FRAME];
	size_t n;
	assert(caseback_encode_frame(msg, payload, size, wire, sizeof(wire), &n) == 0);
	for (size_t i = 0; i < n; ++i)
		printf("%02x", wire[i]);
	puts("");
}

int main(void)
{
	struct history_log log = {0};
	assert(restore(&log) == 0 && log.next == 0);
	activity_test();
	for (unsigned i = 0; i < 8640; ++i)
		assert(history_append(&log, 19, i * 30000ULL, i % 31, false, store) == 0);
	assert(restore(&log) == 0 && log.oldest == 0 && log.next == 8640);
	for (unsigned i = 0; i < log.next; ++i)
		check_epoch(&log, i, 19, i * 30000ULL, i % 31, i == 0);
	uint8_t query[9], data[26];
	uint32_t first;
	assert(history_query(&log, 6, 1, &first, query) == 7 && first == 6 && !query[8]);
	assert(history_payload(&log, 6, 0, data));
	print_frame(CASEBACK_MSG_HISTORY_QUERY, query, sizeof(query));
	print_frame(CASEBACK_MSG_STREAM_DATA, data, sizeof(data));
	puts("72 h simuladas: 8.640 épocas conservadas tras reinicio y consulta completa.");

	write_failure = true;
	assert(history_append(&log, 20, 0, 8, true, store) == -ENOSPC);
	assert(history_acknowledge(&log, 2000, store) == -ENOSPC);
	assert(restore(&log) == 0 && log.next == 8640 && log.acknowledged == 0);
	write_failure = false;
	assert(history_append(&log, 20, 30000, 8, true, store) == 0);
	assert(history_acknowledge(&log, 2000, store) == 0);
	assert(history_acknowledge(&log, 19, store) == 0);
	assert(history_acknowledge(&log, log.next + 1, store) == -ERANGE);
	assert(restore(&log) == 0 && log.next == 8641 && log.acknowledged == 2000);
	check_epoch(&log, 8640, 20, 30000, 8, true);
	puts("Fallos de escritura ensayados en datos y ACK: no avanza ningún cursor; ACK repetido idempotente.");
	for (unsigned i = 1; i < 1000; ++i)
		assert(history_append(&log, 20, (i + 1) * 30000ULL, 7, false, store) == 0);
	assert(restore(&log) == 0 && log.oldest == 96 && log.next == 9640);
	check_epoch(&log, 96, 19, 96 * 30000ULL, 96 % 31, false);
	assert(history_query(&log, 0, 16, &first, query) == 112 && first == 96 && !query[8]);
	log.acknowledged = 12;
	assert(history_query(&log, 10, 0, &first, query) == log.next && first == 96 && query[8]);
	assert(!history_payload(&log, 95, 0, data));
	check_epoch(&log, 9639, 20, 1000 * 30000ULL, 7, false);
	migration_test();
	media[log.newest][1] ^= 0x02;
	assert(restore(&log) == -EINVAL);
	puts("Rotación, reinicio con nuevo boot_id, hueco y CRC de registro dañado comprobados.");
	puts("Contador físico: reposo, cambio de 0,125 g, muestra ausente y recuperación comprobados.");
	return 0;
}
