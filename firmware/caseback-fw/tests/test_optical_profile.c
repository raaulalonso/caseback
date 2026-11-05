#include "optical_profile.h"
#include <assert.h>
#include <stdio.h>

static bool allowed = true, light, fail_on, fail_off, fail_io;
static unsigned starts, stops;
static int64_t clock_ms, sample_time;

bool profile_permitted(void) { return allowed; }
bool profile_led(bool on)
{
	if ((on && fail_on) || (!on && fail_off))
		return false;
	if (on) {
		++starts;
		sample_time = clock_ms;
	} else {
		++stops;
	}
	light = on;
	return true;
}

int profile_green(uint8_t samples[48])
{
	if (fail_io)
		return -1;
	assert(light);
	if (clock_ms - sample_time < 20)
		return 0;
	samples[0] = 0x34;
	samples[1] = 0x12;
	samples[2] = 1;
	sample_time += 20;
	return 1;
}

static uint32_t step(void)
{
	uint32_t delay = optical_tick(clock_ms);
	if (delay != UINT32_MAX)
		clock_ms += delay;
	return delay;
}
static void simulate(uint32_t command, unsigned windows, unsigned switches, unsigned duration)
{
	clock_ms = 0;
	starts = stops = 0;
	caseback_optical_profile[0] = command;
	while (step() != UINT32_MAX)
		assert(clock_ms <= 86400001);
	assert(caseback_optical_profile[1] == 2 && caseback_optical_profile[3] == windows);
	assert(starts == switches && stops == switches && !light);
	assert(clock_ms == duration);
	for (unsigned i = 0; i < windows; ++i) {
		volatile uint32_t *r = caseback_optical_profile + PROFILE_HEADER_WORDS + PROFILE_ROW_WORDS * i;
		assert(r[2] == 0x11234 && r[3] == 0x11234 && r[4] == 0x11234 && r[5] == 0);
		assert(optical_count_ok(r[1], optical_window(command, i).duration_ms));
	}
	printf("%u ventanas, %u arranques de LED, %lld ms y %u muestras sintéticas.\n",
	       windows, switches, (long long)clock_ms, caseback_optical_profile[4]);
}

int main(int argc, char **argv)
{
	assert(optical_tick(0) == UINT32_MAX && !profile_is_active() && !light);
	simulate(PROFILE_SHORT, 4, 4, 50000);
	simulate(PROFILE_DAY_NIGHT, 672, 193, 86400000);
	if (argc == 2) {
		FILE *out = fopen(argv[1], "wb");
		assert(out);
		for (unsigned i = 0; i < PROFILE_HEADER_WORDS + PROFILE_ROW_WORDS * PROFILE_MAX_WINDOWS; ++i) {
			uint32_t word = caseback_optical_profile[i];
			assert(fwrite(&word, sizeof(word), 1, out) == 1);
		}
		assert(fclose(out) == 0);
	}
	allowed = false;
	caseback_optical_profile[0] = PROFILE_SHORT;
	assert(step() == UINT32_MAX && !light && caseback_optical_profile[1] == 0xe1);
	allowed = true;
	fail_on = true;
	caseback_optical_profile[0] = PROFILE_SHORT;
	assert(step() == UINT32_MAX && !light && caseback_optical_profile[1] == 0xe2);
	fail_on = false;
	caseback_optical_profile[0] = PROFILE_SHORT;
	assert(step() == 10 && light);
	allowed = false;
	assert(step() == UINT32_MAX && !light && caseback_optical_profile[1] == 0xe1);
	allowed = true;
	caseback_optical_profile[0] = PROFILE_SHORT;
	assert(step() == 10 && light);
	clock_ms += 500;
	assert(step() == UINT32_MAX && !light && caseback_optical_profile[1] == 0xe3);
	caseback_optical_profile[0] = PROFILE_SHORT;
	assert(step() == 10 && light);
	caseback_optical_profile[0] = PROFILE_STOP;
	assert(step() == UINT32_MAX && !light && caseback_optical_profile[1] == 3);
	caseback_optical_profile[0] = PROFILE_SHORT;
	assert(step() == 10 && light);
	fail_io = fail_off = true;
	assert(step() == UINT32_MAX && caseback_optical_profile[1] == 0xe5);
	assert(caseback_optical_profile[6] == 2);
	puts("Sin armado no hay emisión. Se comprueban parada, interbloqueo, error de bus, tiempo y apagado no confirmado.");
	return 0;
}
