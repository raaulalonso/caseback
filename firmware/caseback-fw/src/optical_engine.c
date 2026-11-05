#include "optical_profile.h"
#include <string.h>

enum { IDLE = 0, RUNNING = 1, FINISHED = 2, ABORTED = 3, INTERLOCK = 0xe1,
       SENSOR_IO = 0xe2, TIMING = 0xe3, SAMPLE_COUNT = 0xe4, UNCONFIRMED_OFF = 0xe5 };

volatile uint32_t caseback_optical_profile[PROFILE_HEADER_WORDS + PROFILE_ROW_WORDS * PROFILE_MAX_WINDOWS];
static uint32_t mode, index_in_run, start_offset;
static int64_t origin, last_sample;
static bool emitting;
static struct optical_counts counts;
bool profile_is_active(void) { return mode != 0; }

static void finish(uint32_t status)
{
	/* Verify SHDN even if the enable transaction failed part-way through. */
	if (!profile_led(false) && !profile_led(false))
		status = UNCONFIRMED_OFF;
	emitting = false;
	mode = 0;
	caseback_optical_profile[1] = status;
	caseback_optical_profile[6] = status == UNCONFIRMED_OFF ? 2 : 0;
}

static bool start_window(uint32_t elapsed, int64_t now)
{
	struct optical_slot slot = optical_window(mode, index_in_run);
	if (elapsed - slot.start_ms > 250) {
		finish(TIMING);
		return false;
	}
	if (!emitting && !profile_led(true)) {
		finish(SENSOR_IO);
		return false;
	}
	emitting = true;
	caseback_optical_profile[6] = 1;
	memset(&counts, 0, sizeof(counts));
	start_offset = elapsed;
	last_sample = now;
	return true;
}

uint32_t optical_tick(int64_t now)
{
	uint32_t request = caseback_optical_profile[0];
	caseback_optical_profile[0] = 0;
	if (!mode) {
		if (!optical_windows(request))
			return UINT32_MAX;
		if (!profile_permitted()) {
			caseback_optical_profile[1] = INTERLOCK;
			return UINT32_MAX;
		}
		/* Payload rows past the committed row count are ignored. */
		for (unsigned i = 1; i < PROFILE_HEADER_WORDS; ++i)
			caseback_optical_profile[i] = 0;
		mode = request;
		origin = now;
		index_in_run = 0;
		start_offset = UINT32_MAX;
		caseback_optical_profile[1] = RUNNING;
		caseback_optical_profile[2] = optical_windows(mode);
	}
	if (request == PROFILE_STOP || !profile_permitted()) {
		finish(request == PROFILE_STOP ? ABORTED : INTERLOCK);
		return UINT32_MAX;
	}
	uint32_t elapsed = (uint32_t)(now - origin);
	struct optical_slot slot = optical_window(mode, index_in_run);
	caseback_optical_profile[5] = elapsed;
	if (elapsed < slot.start_ms) {
		return slot.start_ms - elapsed < 500 ? slot.start_ms - elapsed : 500;
	}
	if (start_offset == UINT32_MAX && !start_window(elapsed, now))
		return UINT32_MAX;
	if (elapsed >= slot.start_ms + slot.duration_ms) {
		if (!optical_count_ok(counts.count, slot.duration_ms)) {
			finish(SAMPLE_COUNT);
			return UINT32_MAX;
		}
		volatile uint32_t *row = &caseback_optical_profile[PROFILE_HEADER_WORDS +
								  PROFILE_ROW_WORDS * index_in_run];
		row[0] = start_offset;
		row[1] = counts.count;
		row[2] = counts.min;
		row[3] = counts.max;
		row[4] = counts.sum / counts.count;
		row[5] = counts.rail;
		caseback_optical_profile[4] += counts.count;
		caseback_optical_profile[3] = ++index_in_run;
		if (index_in_run == optical_windows(mode)) {
			finish(FINISHED);
			return UINT32_MAX;
		}
		if (optical_window(mode, index_in_run).start_ms != slot.start_ms + slot.duration_ms) {
			if (!profile_led(false)) {
				finish(UNCONFIRMED_OFF);
				return UINT32_MAX;
			}
			emitting = false;
			caseback_optical_profile[6] = 0;
		}
		start_offset = UINT32_MAX;
		return 0;
	}
	uint8_t green[48];
	int n = profile_green(green);
	if (n < 0 || now - last_sample > 250) {
		finish(n < 0 ? SENSOR_IO : TIMING);
		return UINT32_MAX;
	}
	for (int i = 0; i < n; ++i)
		optical_add(&counts, (uint32_t)green[3 * i] | (uint32_t)green[3 * i + 1] << 8 |
			    (uint32_t)green[3 * i + 2] << 16);
	if (n)
		last_sample = now;
	caseback_optical_profile[7] = counts.count;
	return 10;
}
