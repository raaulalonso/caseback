#include "factory.h"
#include "protocol.h"
#include <errno.h>
#include <mbedtls/sha256.h>
#include <string.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/kernel.h>
#include <zephyr/random/random.h>
#include <zephyr/settings/settings.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/sys/reboot.h>

static struct factory_record record;
static K_MUTEX_DEFINE(factory_lock);
static atomic_t pending, linked;
static int64_t token_expires;
#define ARM_COMMAND 0x4641524du
#define CLEAR_COMMAND 0x46434c52u
/* SWD only. Word 0 is command/status; the following 16 bytes are transient. */
volatile struct { uint32_t command; uint8_t token[FACTORY_TOKEN_SIZE]; } caseback_factory_fixture;

static int get_record(struct factory_record *out)
{
	int rc = settings_subsys_init();
	if (rc)
		return rc;
	ssize_t size = settings_load_one("cbfac/v1", out, sizeof(*out));
	return size == sizeof(*out) ? 0 : size == 0 ? -ENOENT : -EIO;
}

static int save_record(const struct factory_record *next)
{
	struct factory_record check;
	int rc = settings_save_one("cbfac/v1", next, sizeof(*next));
	if (rc || get_record(&check) || memcmp(&check, next, sizeof(check)))
		return -EIO;
	record = *next;
	return 0;
}

int disc_factory_erase_region(bool history)
{
	const struct flash_area *area;
	int id = history ? FIXED_PARTITION_ID(history_partition) : FIXED_PARTITION_ID(storage_partition);
	int rc = flash_area_open(id, &area);
	if (rc)
		return rc;
	rc = flash_area_flatten(area, 0, area->fa_size);
	uint8_t bytes[128];
	for (off_t off = 0; !rc && off < area->fa_size; off += sizeof(bytes)) {
		rc = flash_area_read(area, off, bytes, sizeof(bytes));
		for (unsigned i = 0; !rc && i < sizeof(bytes); ++i)
			if (bytes[i] != 0xff)
				rc = -EIO;
	}
	flash_area_close(area);
	return rc;
}

static int wipe_settings(void) { return disc_factory_erase_region(false); }
int factory_boot(void)
{
	const struct factory_ops ops = {disc_history_factory_mark, disc_history_factory_save,
		get_record, disc_history_factory_erase, wipe_settings};
	return factory_recover(&ops, &record);
}

static void forget_token(void)
{
	for (unsigned i = 0; i < sizeof(caseback_factory_fixture.token); ++i)
		caseback_factory_fixture.token[i] = 0;
	token_expires = 0;
}

void factory_poll(void)
{
	uint32_t cmd = caseback_factory_fixture.command;
	k_mutex_lock(&factory_lock, K_FOREVER);
	if (cmd == CLEAR_COMMAND || (token_expires && k_uptime_get() >= token_expires)) {
		forget_token();
		caseback_factory_fixture.command = 0;
	} else if (cmd == ARM_COMMAND) {
		forget_token();
		caseback_factory_fixture.command = 0xe1;
		if (factory_armable(&record, disc_dock_level() == 1, atomic_get(&linked), disc_bond_count() != 0)) {
			struct factory_record next;
			uint8_t token[FACTORY_TOKEN_SIZE], digest[FACTORY_DIGEST_SIZE];
			if (!sys_csrand_get(token, sizeof(token)) &&
			    !mbedtls_sha256(token, sizeof(token), digest, 0)) {
				factory_set(&next, FACTORY_ARMED, digest);
				if (!save_record(&next)) {
					for (unsigned i = 0; i < sizeof(token); ++i)
						caseback_factory_fixture.token[i] = token[i];
					token_expires = k_uptime_get() + 60000;
					caseback_factory_fixture.command = 1;
				}
			}
			volatile uint8_t *sensitive = token;
			for (unsigned i = 0; i < sizeof(token); ++i)
				sensitive[i] = 0;
		}
	}
	k_mutex_unlock(&factory_lock);
}

bool factory_pending(void) { return atomic_get(&pending) != 0; }
static void link_up(struct bt_conn *conn, uint8_t err) { if (!err) atomic_set(&linked, 1); }
static void link_down(struct bt_conn *conn, uint8_t reason) { atomic_clear(&linked); }
BT_CONN_CB_DEFINE(factory_connections) = {.connected = link_up, .disconnected = link_down};
static void restart(struct k_work *work) { sys_reboot(SYS_REBOOT_COLD); }
static K_WORK_DELAYABLE_DEFINE(restart_work, restart);

static ssize_t factory_status(struct bt_conn *conn, const struct bt_gatt_attr *attr,
			      void *buf, uint16_t len, uint16_t off)
{
	k_mutex_lock(&factory_lock, K_FOREVER);
	uint8_t value = record.stage == FACTORY_ARMED ? 1 : factory_pending() ? 2 : 0;
	k_mutex_unlock(&factory_lock);
	return bt_gatt_attr_read(conn, attr, buf, len, off, &value, sizeof(value));
}
static ssize_t release(struct bt_conn *conn, const struct bt_gatt_attr *attr,
		       const void *buf, uint16_t len, uint16_t offset, uint8_t flags)
{
	if (offset || len != FACTORY_TOKEN_SIZE)
		return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
	if (flags & (BT_GATT_WRITE_FLAG_PREPARE | BT_GATT_WRITE_FLAG_CMD))
		return BT_GATT_ERR(BT_ATT_ERR_WRITE_NOT_PERMITTED);
	uint8_t digest[FACTORY_DIGEST_SIZE];
	struct bt_conn_info info;
	if (bt_conn_get_info(conn, &info) || bt_conn_get_security(conn) < BT_SECURITY_L2 ||
	    mbedtls_sha256(buf, len, digest, 0))
		return BT_GATT_ERR(BT_ATT_ERR_AUTHORIZATION);
	bool bonded = bt_le_bond_exists(info.id, bt_conn_get_dst(conn));
	k_mutex_lock(&factory_lock, K_FOREVER);
	ssize_t result = BT_GATT_ERR(BT_ATT_ERR_AUTHORIZATION);
	if (factory_matches(&record, digest, disc_dock_level() == 1, bonded)) {
		struct factory_record next;
		factory_set(&next, FACTORY_PENDING, NULL);
		/* Any ambiguous persistence failure also forces a reboot before radio resumes. */
		atomic_set(&pending, 1);
		result = save_record(&next) ? BT_GATT_ERR(BT_ATT_ERR_UNLIKELY) : len;
		forget_token();
		k_work_reschedule(&restart_work, K_MSEC(500));
	}
	k_mutex_unlock(&factory_lock);
	return result;
}

#define FACTORY_UUID(n) BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(n, 0xc131, 0x477f, 0xb22d, 0xe5980935cd62ULL))
BT_GATT_SERVICE_DEFINE(factory_service,
	BT_GATT_PRIMARY_SERVICE(FACTORY_UUID(CASEBACK_FACTORY_SERVICE_W32)),
	BT_GATT_CHARACTERISTIC(FACTORY_UUID(CASEBACK_FACTORY_HANDOVER_W32), BT_GATT_CHRC_READ | BT_GATT_CHRC_WRITE,
		BT_GATT_PERM_READ_ENCRYPT | BT_GATT_PERM_WRITE_ENCRYPT, factory_status, release, NULL));
