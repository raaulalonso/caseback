#include "disc_history.h"
#include "disc.h"
#include "history.h"
#include "factory.h"
#include <errno.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/settings/settings.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/fs/nvs.h>
#include <zephyr/storage/flash_map.h>

static struct history_log logbook;
static struct activity_window window;
static bool ready, pending_reply;
static uint32_t boot_id, replay_cursor, replay_end;
static struct bt_conn *reader, *fast_link;
static int64_t retry_until;
static void restore_interval(struct k_work *work);
static K_WORK_DELAYABLE_DEFINE(idle_work, restore_interval);
static void sample_tick(struct k_work *work);
static void replay_tick(struct k_work *work);
static K_WORK_DELAYABLE_DEFINE(sample_work, sample_tick);
static K_WORK_DELAYABLE_DEFINE(replay_work, replay_tick);

#define HISTORY_NODE DT_NODELABEL(history_partition)
BUILD_ASSERT(DT_REG_SIZE(HISTORY_NODE) == 32 * 4096);
BUILD_ASSERT(!IS_ENABLED(CONFIG_NVS_INIT_BAD_MEMORY_REGION));
static struct nvs_fs history_fs = {
	.flash_device = FIXED_PARTITION_DEVICE(history_partition),
	.offset = DT_REG_ADDR(HISTORY_NODE),
	.sector_size = 4096,
	.sector_count = DT_REG_SIZE(HISTORY_NODE) / 4096,
};

static bool mounted;
static int mount_history(void)
{
	if (!mounted)
		mounted = device_is_ready(history_fs.flash_device) && nvs_mount(&history_fs) == 0;
	return mounted ? 0 : -EIO;
}
#define FACTORY_SEAL_ID (HISTORY_FORMAT_KEY + 2)
int disc_history_factory_mark(uint32_t *mark)
{
	if (mount_history())
		return -EIO;
	uint32_t pair[2];
	int rc = nvs_read(&history_fs, FACTORY_SEAL_ID, pair, sizeof(pair));
	if (rc == -ENOENT) return rc;
	if (rc != sizeof(pair) || pair[0] != ~pair[1]) return -EIO;
	*mark = pair[0];
	return 0;
}
int disc_history_factory_save(uint32_t mark)
{
	uint32_t check, pair[2] = {mark, ~mark};
	if (mount_history() || nvs_write(&history_fs, FACTORY_SEAL_ID, pair, sizeof(pair)) < 0 ||
	    disc_history_factory_mark(&check) || check != mark)
		return -EIO;
	return 0;
}
int disc_history_factory_erase(void)
{
	mounted = false;
	return disc_factory_erase_region(true);
}
static int save_slot(unsigned slot, const void *data, size_t size)
{
	ssize_t rc = nvs_write(&history_fs, slot + 1, data, size);
	return rc < 0 ? (int)rc : 0;
}

static int read_slot(unsigned slot, void *data, size_t size)
{
	return (int)nvs_read(&history_fs, slot + 1, data, size);
}

struct legacy_context { struct history_log *log; bool failed; };

static int restore_slot(const char *key, size_t len, settings_read_cb read_cb,
			void *cb_arg, void *arg)
{
	struct legacy_context *ctx = arg;
	uint8_t bytes[HISTORY_MAX_BYTES];
	int rc = -EINVAL;
	if (key && strlen(key) == 3 && len <= sizeof(bytes) &&
	    key[0] >= '0' && key[0] <= '9' && key[1] >= '0' && key[1] <= '9' &&
	    key[2] >= '0' && key[2] <= '9' && read_cb(cb_arg, bytes, len) == (ssize_t)len) {
		unsigned slot = (key[0] - '0') * 100 + (key[1] - '0') * 10 + key[2] - '0';
		rc = history_load(ctx->log, slot, bytes, len);
	}
	if (rc)
		ctx->failed = true;
	return rc;
}

static int import_legacy(struct history_log *log)
{
	struct legacy_context ctx = {.log = log};
	int rc = settings_load_subtree_direct("cbhist", restore_slot, &ctx);
	return rc || ctx.failed ? -EIO : 0;
}

bool disc_history_init(uint32_t boot)
{
	if (mount_history() ||
	    history_open(&logbook, read_slot, save_slot, import_legacy))
		return false;
	boot_id = boot;
	window.gap = true;
	ready = true;
	k_work_schedule(&sample_work, K_MSEC(1000 - k_uptime_get() % 1000));
	return true;
}

static void sample_tick(struct k_work *work)
{
	int16_t axes[3];
	int64_t now = k_uptime_get();
	bool valid = now % 1000 < 500 && disc_history_sample(axes);
	uint64_t second = (uint64_t)now / 1000;
	if (activity_sample(&window, second, valid ? axes : NULL)) {
		uint64_t start = (second - 29) * 1000;
		window.gap = history_append(&logbook, boot_id, start, window.changes,
					    window.gap, save_slot) != 0;
	}
	k_work_reschedule(&sample_work, K_MSEC(1000 - k_uptime_get() % 1000));
}

static void restore_interval(struct k_work *work)
{
	if (!fast_link)
		return;
	if (!disc_streaming())
		(void)bt_conn_le_param_update(fast_link,
			BT_LE_CONN_PARAM(CASEBACK_CONN_INTERVAL_MIN_MS * 4 / 5,
					 CASEBACK_CONN_INTERVAL_MAX_MS * 4 / 5, 0, 600));
	bt_conn_unref(fast_link);
	fast_link = NULL;
}

static void transfer_active(struct bt_conn *conn)
{
	if (fast_link != conn) {
		if (fast_link)
			bt_conn_unref(fast_link);
		fast_link = bt_conn_ref(conn);
		(void)bt_conn_le_param_update(conn, BT_LE_CONN_PARAM(12, 24, 0, 600));
	}
	k_work_reschedule(&idle_work, K_SECONDS(3));
}

static void stop_replay(void)
{
	k_work_cancel_delayable(&replay_work);
	pending_reply = false;
	if (reader) {
		bt_conn_unref(reader);
		reader = NULL;
	}
}

int disc_history_request(struct bt_conn *conn, const struct caseback_frame *f,
			 uint8_t *payload, size_t *len)
{
	if (!ready || bt_conn_get_security(conn) < BT_SECURITY_L2)
		return CASEBACK_ERR_BAD_STATE;
	if (f->payload_len != (f->msg_type == CASEBACK_MSG_HISTORY_ACK ? 4 : 6))
		return CASEBACK_ERR_BAD_PAYLOAD_LENGTH;
	uint32_t cursor = sys_get_le32(f->payload);
	if (cursor > logbook.next)
		return CASEBACK_ERR_CURSOR_OUT_OF_RANGE;
	if (f->msg_type == CASEBACK_MSG_HISTORY_ACK) {
		*len = 0;
		return history_acknowledge(&logbook, cursor, save_slot) ? CASEBACK_ERR_INTERNAL : 0;
	}
	stop_replay();
	if (bt_gatt_get_mtu(conn) < 36)
		return CASEBACK_ERR_BAD_STATE;
	uint16_t limit = sys_get_le16(f->payload + 4);
	replay_end = history_query(&logbook, cursor, limit, &replay_cursor, payload);
	*len = 9;
	if (replay_cursor < replay_end) {
		reader = bt_conn_ref(conn);
		transfer_active(conn);
		retry_until = k_uptime_get() + 5000;
		pending_reply = true;
	}
	return 0;
}

void disc_history_replied(struct bt_conn *conn, bool success)
{
	if (!pending_reply || reader != conn)
		return;
	pending_reply = false;
	if (success)
		k_work_reschedule(&replay_work, K_NO_WAIT);
	else
		stop_replay();
}

static void replay_tick(struct k_work *work)
{
	uint8_t p[26], wire[CASEBACK_MAX_FRAME];
	size_t n;
	struct bt_conn_info info;
	if (!reader || bt_conn_get_info(reader, &info) || info.state != BT_CONN_STATE_CONNECTED ||
	    !history_payload(&logbook, replay_cursor, disc_sequence(), p)) {
		stop_replay();
		return;
	}
	int rc = caseback_encode_frame(CASEBACK_MSG_STREAM_DATA, p, sizeof(p), wire, sizeof(wire), &n);
	if (!rc)
		rc = disc_notify(reader, wire, n);
	if ((rc == -ENOMEM || rc == -EAGAIN || rc == -ENOBUFS) && k_uptime_get() < retry_until) {
		transfer_active(reader);
		k_work_reschedule(&replay_work, K_MSEC(40));
		return;
	}
	if (!rc) {
		disc_sequence_sent();
		++replay_cursor;
		transfer_active(reader);
		retry_until = k_uptime_get() + 5000;
	}
	if (rc || replay_cursor == replay_end) {
		stop_replay();
		return;
	}
	k_work_reschedule(&replay_work, K_MSEC(15));
}
