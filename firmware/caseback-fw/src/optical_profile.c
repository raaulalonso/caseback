#include "optical_profile.h"
#include <zephyr/kernel.h>

static void run_profile(struct k_work *work);
static K_WORK_DELAYABLE_DEFINE(profile_work, run_profile);

static void run_profile(struct k_work *work)
{
	uint32_t delay = optical_tick(k_uptime_get());
	if (delay != UINT32_MAX)
		k_work_reschedule(&profile_work, K_MSEC(delay));
}

void profile_check_request(void)
{
	if (caseback_optical_profile[0])
		k_work_reschedule(&profile_work, K_NO_WAIT);
}
