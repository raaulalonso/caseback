#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define FACTORY_TOKEN_SIZE 16
#define FACTORY_DIGEST_SIZE 32

enum factory_stage { FACTORY_NEW, FACTORY_ARMED, FACTORY_PENDING, FACTORY_DONE };
enum factory_mark { FACTORY_NO_MARK, FACTORY_WIPE_SETTINGS = 0x46435731, FACTORY_SEALED = 0x46435331 };
struct factory_record { uint32_t stage; uint8_t digest[FACTORY_DIGEST_SIZE]; uint32_t crc; };
struct factory_ops {
	int (*mark_read)(uint32_t *);
	int (*mark_save)(uint32_t);
	int (*state_read)(struct factory_record *);
	int (*history_erase)(void);
	int (*settings_erase)(void);
};
enum factory_result { FACTORY_READY, FACTORY_RETIRED };
int factory_recover(const struct factory_ops *ops, struct factory_record *record);
void factory_set(struct factory_record *record, enum factory_stage stage, const uint8_t *digest);
bool factory_matches(const struct factory_record *record, const uint8_t *digest,
		     bool docked, bool bonded);
bool factory_armable(const struct factory_record *record, bool docked, bool linked, bool bonded);
int factory_boot(void);
void factory_poll(void);
bool factory_pending(void);
unsigned disc_bond_count(void);
int disc_dock_level(void);
void disc_poweroff(bool wake_high);
int disc_history_factory_mark(uint32_t *mark);
int disc_history_factory_save(uint32_t mark);
int disc_history_factory_erase(void);
int disc_factory_erase_region(bool history);

bool factory_should_sleep(bool optical_lab, unsigned bonds, int dock);
