#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define HISTORY_SLOTS 100
#define EPOCHS_PER_PAGE 96
#define HISTORY_EPOCH_MS 30000
#define HISTORY_ACK_KEY HISTORY_SLOTS

/* Private NVS schema v1. Nordic and the supported test hosts are little-endian.
 * Every update replaces one NVS value atomically; its checksum covers the data. */
struct history_page {
	uint64_t uptime;
	uint32_t boot, first;
	uint8_t count, version, activity[EPOCHS_PER_PAGE];
} __attribute__((packed));

#define HISTORY_MAX_BYTES (sizeof(struct history_page) + sizeof(uint16_t))

struct history_ack {
	uint32_t cursor;
	uint16_t crc;
} __attribute__((packed));

struct history_log {
	struct history_page pages[HISTORY_SLOTS];
	uint32_t oldest, next, acknowledged;
	unsigned newest;
};

typedef int (*history_write)(unsigned key, const void *data, size_t size);

struct activity_window {
	uint64_t second;
	int16_t axes[3];
	unsigned count, changes;
	bool previous, gap;
};

int history_load(struct history_log *log, unsigned key, const void *data, size_t size);
int history_recover(struct history_log *log);
int history_append(struct history_log *log, uint32_t boot, uint64_t uptime,
		   unsigned activity, bool gap, history_write write);
int history_acknowledge(struct history_log *log, uint32_t cursor, history_write write);
bool history_epoch(const struct history_log *log, uint32_t cursor, uint32_t *boot,
		   uint64_t *uptime, uint8_t *activity, bool *gap);
bool activity_sample(struct activity_window *window, uint64_t second, const int16_t *axes);

/* Payloads from the existing HISTORY_QUERY and STREAM_DATA/EPOCH definitions. */
uint32_t history_query(const struct history_log *log, uint32_t cursor, uint16_t limit,
		       uint32_t *first, uint8_t payload[9]);
bool history_payload(const struct history_log *log, uint32_t cursor, uint16_t seq,
		     uint8_t payload[26]);

#define HISTORY_FORMAT_KEY (HISTORY_ACK_KEY + 1)
typedef int (*history_read)(unsigned key, void *data, size_t size);
int history_open(struct history_log *log, history_read read, history_write write,
		 int (*legacy)(struct history_log *));
