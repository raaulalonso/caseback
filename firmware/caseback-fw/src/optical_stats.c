#include "optical_profile.h"

unsigned optical_windows(uint32_t command)
{
	return command == PROFILE_SHORT ? 4 : command == PROFILE_DAY_NIGHT ? PROFILE_MAX_WINDOWS : 0;
}

struct optical_slot optical_window(uint32_t command, unsigned i)
{
	if (i >= optical_windows(command))
		return (struct optical_slot){0, 0};
	if (command == PROFILE_SHORT)
		return (struct optical_slot){15000 * i, 5000};
	if (i < 192)
		return (struct optical_slot){300000 * i, 30000};
	return (struct optical_slot){57600000 + (i - 192) * 60000, 60000};
}

void optical_add(struct optical_counts *s, uint32_t adc)
{
	if (!s->count || adc < s->min)
		s->min = adc;
	if (!s->count || adc > s->max)
		s->max = adc;
	s->sum += adc;
	++s->count;
	s->rail += adc == 0 || adc == 0x7ffff;
}

bool optical_count_ok(uint32_t count, uint32_t duration_ms)
{
	/* 50 samples/s nominal, +/- 10% scheduling and setup acceptance window. */
	return 2000ULL * count >= 90ULL * duration_ms &&
		2000ULL * count <= 110ULL * duration_ms;
}
