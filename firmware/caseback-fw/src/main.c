/* Caseback V0 bring-up firmware.
 *
 * NOT BUILT YET: written without a Zephyr/NCS toolchain. API names assume
 * Zephyr 4.x / NCS 3.x (marked below where older trees differ). Pin the
 * version and build first, see README.md.
 */
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/version.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/drivers/hwinfo.h>
#include <zephyr/drivers/watchdog.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/settings/settings.h>
#include <zephyr/logging/log.h>

#include "device.h"
#include "protocol.h"

LOG_MODULE_REGISTER(caseback, LOG_LEVEL_INF);

/* BMI270 on I2C (SDO low = 0x68). CHIP_ID register 0x00 reads 0x24 (BMI270
 * datasheet, from memory: log it, do not trust it until checked on the bench).
 */
#define BMI270_ADDR 0x68
#define BMI270_REG_CHIP_ID 0x00

#define I2C_NODE DT_NODELABEL(arduino_i2c)
#define AFE_NODE DT_NODELABEL(max86140)
#define USER_NODE DT_PATH(zephyr_user)

/* Loop period: LED pulse + watchdog feed. The watchdog only proves that the
 * main thread runs, not that the BLE stack is healthy.
 */
#define STATUS_PERIOD_MS 2000
#define LED_PULSE_MS 20
#define WDT_TIMEOUT_MS 10000

/* Advertising interval, units of 0.625 ms: 100 to 150 ms. */
#define ADV_INT_MIN 0x00A0
#define ADV_INT_MAX 0x00F0

#if DT_NODE_HAS_STATUS(I2C_NODE, okay)
static const struct device *const i2c_dev = DEVICE_DT_GET(I2C_NODE);
#else
static const struct device *const i2c_dev = NULL;
#endif

#if DT_NODE_EXISTS(DT_ALIAS(led0))
#define HAVE_LED 1
static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);
#endif

/* Zephyr 4.0+ dropped the delay argument of SPI_DT_SPEC_GET (assumed
 * threshold, check against the pinned tree).
 */
#if DT_NODE_EXISTS(AFE_NODE)
#define HAVE_AFE 1
#if ZEPHYR_VERSION_CODE >= ZEPHYR_VERSION(4, 0, 0)
static const struct spi_dt_spec afe_spi =
	SPI_DT_SPEC_GET(AFE_NODE, SPI_WORD_SET(8) | SPI_TRANSFER_MSB);
#else
static const struct spi_dt_spec afe_spi =
	SPI_DT_SPEC_GET(AFE_NODE, SPI_WORD_SET(8) | SPI_TRANSFER_MSB, 0);
#endif
static const struct gpio_dt_spec afe_int = GPIO_DT_SPEC_GET(USER_NODE, afe_int_gpios);
#endif

static const struct device *const wdt = DEVICE_DT_GET_OR_NULL(DT_ALIAS(watchdog0));

/* Caseback GATT (spec/gatt.md): INFO read, CONTROL write-without-response
 * (phone to device), DATA notify (device to phone). UUIDs from protocol.h.
 */
#define CASEBACK_UUID_ARGS(w32) w32, CASEBACK_UUID_W1, CASEBACK_UUID_W2, CASEBACK_UUID_W3, CASEBACK_UUID_W48

static struct bt_uuid_128 caseback_svc_uuid =
	BT_UUID_INIT_128(BT_UUID_128_ENCODE(CASEBACK_UUID_ARGS(CASEBACK_UUID_SERVICE_W32)));
static struct bt_uuid_128 caseback_info_uuid =
	BT_UUID_INIT_128(BT_UUID_128_ENCODE(CASEBACK_UUID_ARGS(CASEBACK_UUID_INFO_W32)));
static struct bt_uuid_128 caseback_control_uuid =
	BT_UUID_INIT_128(BT_UUID_128_ENCODE(CASEBACK_UUID_ARGS(CASEBACK_UUID_CONTROL_W32)));
static struct bt_uuid_128 caseback_data_uuid =
	BT_UUID_INIT_128(BT_UUID_128_ENCODE(CASEBACK_UUID_ARGS(CASEBACK_UUID_DATA_W32)));

static struct caseback_info info;
static char adv_name[CASEBACK_NAME_MAX];

/* Advertising data: flags + 128-bit service UUID (iOS background scan needs
 * it in the advertisement). The per-unit name goes in the scan response.
 */
static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
	BT_DATA_BYTES(BT_DATA_UUID128_ALL,
		      BT_UUID_128_ENCODE(CASEBACK_UUID_ARGS(CASEBACK_UUID_SERVICE_W32))),
};
static struct bt_data sd[1];

/* Not BT_LE_ADV_CONN_NAME (deprecated). ONE_TIME so that we restart
 * advertising ourselves after a disconnect instead of relying on stack
 * behaviour that differs between versions.
 */
static const struct bt_le_adv_param adv_param = BT_LE_ADV_PARAM_INIT(
	BT_LE_ADV_OPT_CONNECTABLE | BT_LE_ADV_OPT_ONE_TIME, ADV_INT_MIN, ADV_INT_MAX, NULL);

static atomic_t adv_active;
static atomic_t link_up;
static atomic_ptr_t link_conn; /* ref held until the link work runs or the link drops */
static bool bt_ready;

#ifdef CONFIG_CASEBACK_REQUIRE_ENCRYPTION
#define INFO_READ_PERM BT_GATT_PERM_READ_ENCRYPT
#define CONTROL_WRITE_PERM BT_GATT_PERM_WRITE_ENCRYPT
#define DATA_CCC_PERM (BT_GATT_PERM_READ_ENCRYPT | BT_GATT_PERM_WRITE_ENCRYPT)
#else
#define INFO_READ_PERM BT_GATT_PERM_READ
#define CONTROL_WRITE_PERM BT_GATT_PERM_WRITE
#define DATA_CCC_PERM (BT_GATT_PERM_READ | BT_GATT_PERM_WRITE)
#endif

/* Largest CONTROL value: ATT MTU - 3. Writes are queued here and handled on
 * the system workqueue, so the BT callback does no blocking work (a notify
 * can wait for a TX buffer).
 */
#define CONTROL_MAX_WRITE (CASEBACK_ATT_MTU_REQUESTED - 3)
#define CONTROL_QUEUE_DEPTH 2

struct control_msg {
	struct bt_conn *conn; /* referenced */
	uint16_t len;
	uint8_t data[CONTROL_MAX_WRITE];
};

K_MSGQ_DEFINE(control_q, sizeof(struct control_msg), CONTROL_QUEUE_DEPTH, 4);
static void control_work_fn(struct k_work *work);
static K_WORK_DEFINE(control_work, control_work_fn);

static ssize_t read_info(struct bt_conn *conn, const struct bt_gatt_attr *attr,
			 void *buf, uint16_t len, uint16_t offset)
{
	uint8_t frame[CASEBACK_MAX_FRAME];
	size_t frame_len = 0;

	if (caseback_build_info_frame(frame, sizeof(frame), &frame_len, &info) != CASEBACK_OK) {
		return BT_GATT_ERR(BT_ATT_ERR_UNLIKELY);
	}
	return bt_gatt_attr_read(conn, attr, buf, len, offset, frame, frame_len);
}

static ssize_t write_control(struct bt_conn *conn, const struct bt_gatt_attr *attr,
			     const void *buf, uint16_t len, uint16_t offset, uint8_t flags)
{
	struct control_msg msg;

	if (offset != 0 || len > sizeof(msg.data)) {
		return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
	}
	msg.conn = bt_conn_ref(conn);
	msg.len = len;
	memcpy(msg.data, buf, len);
	if (k_msgq_put(&control_q, &msg, K_NO_WAIT) != 0) {
		LOG_WRN("CONTROL queue full, frame dropped");
		bt_conn_unref(msg.conn);
		return len;
	}
	k_work_submit(&control_work);
	return len;
}

static void data_ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
	LOG_INF("DATA notifications %s", value == BT_GATT_CCC_NOTIFY ? "on" : "off");
}

BT_GATT_SERVICE_DEFINE(
	caseback_svc, BT_GATT_PRIMARY_SERVICE(&caseback_svc_uuid.uuid),
	BT_GATT_CHARACTERISTIC(&caseback_info_uuid.uuid, BT_GATT_CHRC_READ, INFO_READ_PERM,
			       read_info, NULL, NULL),
	BT_GATT_CHARACTERISTIC(&caseback_control_uuid.uuid, BT_GATT_CHRC_WRITE_WITHOUT_RESP,
			       CONTROL_WRITE_PERM, NULL, write_control, NULL),
	BT_GATT_CHARACTERISTIC(&caseback_data_uuid.uuid, BT_GATT_CHRC_NOTIFY, BT_GATT_PERM_NONE,
			       NULL, NULL, NULL),
	BT_GATT_CCC(data_ccc_changed, DATA_CCC_PERM));

static void control_work_fn(struct k_work *work)
{
	struct control_msg msg;
	uint8_t reply[CASEBACK_MAX_FRAME];
	size_t reply_len = 0;

	while (k_msgq_get(&control_q, &msg, K_NO_WAIT) == 0) {
		if (caseback_handle_control(&info, msg.data, msg.len, reply, sizeof(reply),
					 &reply_len) != CASEBACK_OK) {
			LOG_ERR("no reply for a %u byte CONTROL write", msg.len);
		} else if (reply_len > (size_t)(bt_gatt_get_mtu(msg.conn) - 3)) {
			/* never truncate a frame: the phone has not exchanged the MTU yet */
			LOG_WRN("reply of %u bytes exceeds ATT MTU %u, dropped", (unsigned)reply_len,
				(unsigned)bt_gatt_get_mtu(msg.conn));
		} else {
			int rc = bt_gatt_notify_uuid(msg.conn, &caseback_data_uuid.uuid, caseback_svc.attrs,
						     reply, reply_len);

			if (rc) {
				LOG_WRN("DATA notify failed %d", rc);
			}
		}
		bt_conn_unref(msg.conn);
	}
}

static int adv_start(void)
{
	int rc = bt_le_adv_start(&adv_param, ad, ARRAY_SIZE(ad), sd, ARRAY_SIZE(sd));

	if (rc == 0) {
		atomic_set(&adv_active, 1);
		LOG_INF("advertising as %s", adv_name);
	} else {
		atomic_set(&adv_active, 0);
		LOG_ERR("adv start failed %d", rc);
	}
	return rc;
}

/* ATT MTU request (the size itself comes from CONFIG_BT_L2CAP_TX_MTU),
 * data length and connection parameters, done off the BT callback.
 */
BUILD_ASSERT(CONFIG_BT_L2CAP_TX_MTU >= CASEBACK_ATT_MTU_REQUESTED, "L2CAP TX MTU below the protocol");
BUILD_ASSERT(CONFIG_BT_PERIPHERAL_PREF_MIN_INT == CASEBACK_CONN_INTERVAL_MIN_MS * 4 / 5 &&
		     CONFIG_BT_PERIPHERAL_PREF_MAX_INT == CASEBACK_CONN_INTERVAL_MAX_MS * 4 / 5 &&
		     CONFIG_BT_PERIPHERAL_PREF_LATENCY == CASEBACK_CONN_LATENCY &&
		     CONFIG_BT_PERIPHERAL_PREF_TIMEOUT == CASEBACK_CONN_SUPERVISION_TIMEOUT_MS / 10,
	     "prj.conf connection parameters differ from protocol.h");

static void mtu_done(struct bt_conn *conn, uint8_t err, struct bt_gatt_exchange_params *params)
{
	LOG_INF("MTU exchange %s, ATT MTU %u", err ? "failed" : "done",
		(unsigned)bt_gatt_get_mtu(conn));
}

static struct bt_gatt_exchange_params mtu_params = {.func = mtu_done};

static void link_work_fn(struct k_work *work)
{
	struct bt_conn *conn = atomic_ptr_clear(&link_conn);
	int rc;

	if (conn == NULL) {
		return;
	}
	rc = bt_gatt_exchange_mtu(conn, &mtu_params);
	if (rc) {
		LOG_WRN("MTU exchange request failed %d", rc);
	}
	if (IS_ENABLED(CONFIG_BT_USER_DATA_LEN_UPDATE)) {
		rc = bt_conn_le_data_len_update(conn, BT_LE_DATA_LEN_PARAM_MAX);
		if (rc) {
			LOG_WRN("data length update failed %d", rc);
		}
	}
	/* interval in 1.25 ms units, timeout in 10 ms units */
	rc = bt_conn_le_param_update(conn, BT_LE_CONN_PARAM(CASEBACK_CONN_INTERVAL_MIN_MS * 4 / 5,
							    CASEBACK_CONN_INTERVAL_MAX_MS * 4 / 5,
							    CASEBACK_CONN_LATENCY,
							    CASEBACK_CONN_SUPERVISION_TIMEOUT_MS / 10));
	if (rc) {
		LOG_WRN("connection parameter update failed %d", rc);
	}
	bt_conn_unref(conn);
}

static K_WORK_DEFINE(link_work, link_work_fn);

static void on_connected(struct bt_conn *conn, uint8_t err)
{
	atomic_set(&adv_active, 0);
	if (err) {
		LOG_ERR("connect failed 0x%02x", err);
		return;
	}
	atomic_set(&link_up, 1);
	atomic_ptr_set(&link_conn, bt_conn_ref(conn));
	k_work_submit(&link_work);
	LOG_INF("connected");
}

static void on_disconnected(struct bt_conn *conn, uint8_t reason)
{
	struct bt_conn *pending = atomic_ptr_clear(&link_conn);

	if (pending != NULL) {
		bt_conn_unref(pending);
	}
	atomic_set(&link_up, 0);
	LOG_INF("disconnected, reason 0x%02x", reason);
}

/* With BT_MAX_CONN=1 the connection object is only free once it is recycled,
 * so advertising restarts here (after disconnected); the main loop retries if
 * this fails.
 */
static void on_recycled(void)
{
	(void)adv_start();
}

BT_CONN_CB_DEFINE(conn_cbs) = {
	.connected = on_connected,
	.disconnected = on_disconnected,
	.recycled = on_recycled,
};

static void probe_bmi270(void)
{
	uint8_t id;

	if (i2c_dev == NULL || !device_is_ready(i2c_dev)) {
		LOG_ERR("I2C not ready");
		return;
	}
	if (i2c_reg_read_byte(i2c_dev, BMI270_ADDR, BMI270_REG_CHIP_ID, &id) == 0) {
		LOG_INF("BMI270 @0x%02x CHIP_ID=0x%02x", BMI270_ADDR, id);
	} else {
		LOG_WRN("no I2C device at 0x%02x", BMI270_ADDR);
	}
}

static void probe_afe(void)
{
#ifdef HAVE_AFE
	uint8_t tx[CASEBACK_AFE_SPI_FRAME_LEN];
	uint8_t rx[CASEBACK_AFE_SPI_FRAME_LEN] = {0};
	const struct spi_buf txb = {.buf = tx, .len = sizeof(tx)};
	const struct spi_buf rxb = {.buf = rx, .len = sizeof(rx)};
	const struct spi_buf_set txs = {.buffers = &txb, .count = 1};
	const struct spi_buf_set rxs = {.buffers = &rxb, .count = 1};
	const char *part;
	int rc;

	if (!spi_is_ready_dt(&afe_spi)) {
		LOG_ERR("SPI not ready");
		return;
	}
	if (gpio_is_ready_dt(&afe_int)) {
		(void)gpio_pin_configure_dt(&afe_int, GPIO_INPUT);
	}

	caseback_afe_build_read(CASEBACK_AFE_REG_PART_ID, tx);
	rc = spi_transceive_dt(&afe_spi, &txs, &rxs);
	if (rc) {
		LOG_ERR("AFE SPI transfer failed %d", rc);
		return;
	}
	/* Data byte is the third one of the frame. */
	part = caseback_afe_part_name(rx[2]);
	if (part != NULL) {
		LOG_INF("AFE PART_ID=0x%02x (%s)", rx[2], part);
	} else {
		/* 0x00/0xFF usually means no device, wiring, 1.8 V level or SPI mode. */
		LOG_WRN("AFE PART_ID=0x%02x, expected 0x%02x/0x%02x", rx[2],
			CASEBACK_AFE_PART_ID_MAX86140, CASEBACK_AFE_PART_ID_MAX86141);
	}
#else
	LOG_WRN("no max86140 node in the devicetree");
#endif
}

static void wdt_start(int *channel)
{
	const struct wdt_timeout_cfg cfg = {
		.window = {.min = 0, .max = WDT_TIMEOUT_MS},
		.callback = NULL,
		.flags = WDT_FLAG_RESET_SOC,
	};

	*channel = -1;
	if (wdt == NULL || !device_is_ready(wdt)) {
		LOG_WRN("no watchdog");
		return;
	}
	*channel = wdt_install_timeout(wdt, &cfg);
	if (*channel < 0 || wdt_setup(wdt, WDT_OPT_PAUSE_HALTED_BY_DBG) != 0) {
		LOG_ERR("watchdog setup failed %d", *channel);
		*channel = -1;
	}
}

static void led_pulse(void)
{
#ifdef HAVE_LED
	gpio_pin_set_dt(&led, 1);
	k_msleep(LED_PULSE_MS);
	gpio_pin_set_dt(&led, 0);
#else
	k_msleep(LED_PULSE_MS);
#endif
}

int main(void)
{
	uint8_t raw_id[CASEBACK_DEVICE_ID_LEN] = {0};
	int wdt_ch;
	int rc;

	LOG_INF("Caseback bring-up");

#ifdef HAVE_LED
	if (!gpio_is_ready_dt(&led) || gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE)) {
		LOG_WRN("LED not available");
	}
#endif

	/* device_id from the hardware id (nRF: FICR DEVICEID, 8 bytes). */
	rc = hwinfo_get_device_id(raw_id, sizeof(raw_id));
	if (rc <= 0) {
		LOG_ERR("hwinfo_get_device_id failed %d", rc);
	}
	caseback_device_id_normalize(info.device_id, raw_id, rc);
	info.hw_rev = CONFIG_CASEBACK_HW_REV;
	info.fw_rev = CONFIG_CASEBACK_FW_REV;
	info.capabilities = caseback_capabilities(CASEBACK_IMPLEMENTED_CAPS,
					       IS_ENABLED(CONFIG_CASEBACK_REQUIRE_ENCRYPTION));
	(void)caseback_build_name(adv_name, sizeof(adv_name), info.device_id);

	probe_bmi270();
	probe_afe();
	wdt_start(&wdt_ch);

	rc = bt_enable(NULL);
	if (rc) {
		LOG_ERR("bt_enable failed %d", rc);
	} else {
		bt_ready = true;
		if (IS_ENABLED(CONFIG_BT_SETTINGS)) {
			(void)settings_load();
		}
		if (IS_ENABLED(CONFIG_BT_DEVICE_NAME_DYNAMIC)) {
			(void)bt_set_name(adv_name);
		}
		sd[0].type = BT_DATA_NAME_COMPLETE;
		sd[0].data = (const uint8_t *)adv_name;
		sd[0].data_len = (uint8_t)strlen(adv_name);
		(void)adv_start();
	}

	/* Never return: keep the status pulse and the watchdog alive so a BLE
	 * failure stays visible (and retried) instead of silently stopping.
	 */
	while (1) {
		if (wdt_ch >= 0) {
			(void)wdt_feed(wdt, wdt_ch);
		}
		if (bt_ready && !atomic_get(&adv_active) && !atomic_get(&link_up)) {
			LOG_WRN("advertising not active, retrying");
			(void)adv_start();
		}
		led_pulse();
		k_msleep(STATUS_PERIOD_MS - LED_PULSE_MS);
	}
	return 0;
}
