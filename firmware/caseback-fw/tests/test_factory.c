#include "factory.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

static struct factory_record settings;
static uint32_t mark;
static bool empty_settings, journal_bad, settings_bad, has_samples = true, has_bond = true;
static unsigned step_count, cut_at, phase, erased_settings, erased_history;
static bool cut(unsigned when) { return step_count == cut_at && phase == when; }
static int read_mark(uint32_t *out)
{
	if (journal_bad) return -EIO;
	if (!mark) return -ENOENT;
	*out = mark;
	return 0;
}
static int write_mark(uint32_t value)
{
	++step_count;
	if (cut(0) || cut(1)) return -EIO; /* NVS metadata is appended after the value */
	mark = value;
	return cut(2) ? -EIO : 0;
}
static int read_state(struct factory_record *out)
{
	if (settings_bad) return -EIO;
	if (empty_settings) return -ENOENT;
	*out = settings;
	return 0;
}
static int erase_data(void)
{
	++step_count;
	++erased_history;
	if (cut(0)) return -EIO;
	if (cut(1)) { journal_bad = true; return -EIO; }
	mark = 0;
	has_samples = journal_bad = false;
	return cut(2) ? -EIO : 0;
}
static int erase_keys(void)
{
	++step_count;
	++erased_settings;
	if (cut(0)) return -EIO;
	if (cut(1)) { settings_bad = true; return -EIO; }
	has_bond = settings_bad = false;
	empty_settings = true;
	memset(&settings, 0xff, sizeof(settings));
	return cut(2) ? -EIO : 0;
}
static const struct factory_ops ops = {read_mark, write_mark, read_state, erase_data, erase_keys};

int main(void)
{
	uint8_t digest[FACTORY_DIGEST_SIZE] = {9}, wrong[FACTORY_DIGEST_SIZE] = {0};
	struct factory_record r;
	empty_settings = true;
	assert(factory_recover(&ops,&r)==FACTORY_READY && r.stage==FACTORY_NEW);
	assert(factory_armable(&r, true, false, false));
	assert(!factory_armable(&r, false, false, false));
	assert(!factory_armable(&r, true, true, false));
	assert(!factory_armable(&r, true, false, true));
	empty_settings = false;
	factory_set(&settings, FACTORY_ARMED, digest);
	assert(factory_recover(&ops,&r)==FACTORY_READY && r.stage==FACTORY_ARMED);
	assert(!factory_matches(&r,wrong,true,true));
	assert(!factory_matches(&r,digest,false,true) && !factory_matches(&r,digest,true,false));
	assert(factory_matches(&r,digest,true,true));
	settings.crc ^= 1;
	assert(factory_recover(&ops,&r)<0 && !erased_settings && !erased_history);
	settings.crc ^= 1;
	mark=42;
	assert(factory_recover(&ops,&r)<0 && !erased_settings && !erased_history);

	for (unsigned n=1; n<=4; ++n) {
		for (unsigned at=0; at<3; ++at) {
			journal_bad = settings_bad = empty_settings = false;
			has_bond = has_samples = true;
			mark = step_count = 0;
			cut_at=n; phase=at;
			factory_set(&settings, FACTORY_PENDING, NULL);
			assert(factory_recover(&ops,&r)<0);
			cut_at=0;
			int result = factory_recover(&ops,&r);
			assert(result>=0 && r.stage==FACTORY_DONE && mark==FACTORY_SEALED);
			assert(!has_samples && !has_bond && empty_settings);
			assert(!factory_matches(&r,digest,true,true) && !factory_armable(&r,true,false,false));
			/* The new user's first bond and log must survive later starts and stale tokens. */
			has_samples=has_bond=true;
			assert(factory_recover(&ops,&r)==FACTORY_READY && has_samples && has_bond);
		}
	}
	assert(factory_should_sleep(false,0,0) && factory_should_sleep(false,0,-EIO));
	assert(!factory_should_sleep(false,0,1) && !factory_should_sleep(false,1,0));
	assert(!factory_should_sleep(true,0,0));
	puts("12 cuts before, during and after four erase/marker operations; old samples and bonds purged, new owner's data retained.");
	puts("Missing dock, missing bond, wrong digest, consumed token and corrupt state fail closed; wake policy separates unowned, bonded and bench states.");
}
