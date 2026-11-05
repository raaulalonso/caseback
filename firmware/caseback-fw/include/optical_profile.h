#pragma once

#include <stdbool.h>
#include <stdint.h>

#define PROFILE_SHORT 0x50534631u
#define PROFILE_DAY_NIGHT 0x50534632u
#define PROFILE_STOP 0x53544f50u
#define PROFILE_MAX_WINDOWS 672u
#define PROFILE_HEADER_WORDS 8u
#define PROFILE_ROW_WORDS 6u

struct optical_slot { uint32_t start_ms, duration_ms; };
struct optical_counts {
	uint64_t sum;
	uint32_t count, min, max, rail;
};

unsigned optical_windows(uint32_t command);
struct optical_slot optical_window(uint32_t command, unsigned index);
void optical_add(struct optical_counts *stats, uint32_t adc);
bool optical_count_ok(uint32_t count, uint32_t duration_ms);
void profile_check_request(void);
bool profile_is_active(void);
bool profile_permitted(void);
bool profile_led(bool enable);
int profile_green(uint8_t samples[48]);

extern volatile uint32_t caseback_optical_profile[PROFILE_HEADER_WORDS + PROFILE_ROW_WORDS * PROFILE_MAX_WINDOWS];
uint32_t optical_tick(int64_t now);
