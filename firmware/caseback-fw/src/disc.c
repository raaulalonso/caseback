#include "disc.h"
#include "disc_history.h"
#include "factory.h"
#include <zephyr/sys/poweroff.h>
#include <zephyr/sys/reboot.h>
#ifdef CONFIG_CASEBACK_OPTICAL_PROFILE
#include "optical_profile.h"
#endif
#include "bench_data.h"
#include <errno.h>
#include <string.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/kernel.h>
#include <zephyr/random/random.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/atomic.h>

#ifdef CONFIG_CASEBACK_OPTICAL_PROFILE
static atomic_t profile_radio;
#endif
#define USER DT_PATH(zephyr_user)
static const struct gpio_dt_spec dock = GPIO_DT_SPEC_GET(USER, dock_gpios);
static const struct gpio_dt_spec charge = GPIO_DT_SPEC_GET(USER, charge_gpios);
static const struct gpio_dt_spec fault = GPIO_DT_SPEC_GET(USER, fault_gpios);
static const struct adc_dt_spec battery_adc = ADC_DT_SPEC_GET(USER);
static const struct spi_dt_spec afe =
    SPI_DT_SPEC_GET(DT_NODELABEL(max86140), SPI_WORD_SET(8), 1);
static const struct device *const bus = DEVICE_DT_GET(DT_NODELABEL(disc_i2c));
static const struct device *const imu = DEVICE_DT_GET(DT_NODELABEL(imu));
static bool valid_adc, valid_gpio, valid_boot, valid_temp;
static uint32_t boot_id, caps;
static volatile uint64_t last_utc;
static struct bt_conn *owner;
static bool running[3], gap[3], active_interval;
static int64_t expires[3], last_acc;
static atomic_t seq;
static bool history_imu;
uint16_t disc_sequence(void) { return (uint16_t)atomic_get(&seq); }
void disc_sequence_sent(void) { atomic_inc(&seq); }
bool disc_streaming(void) { return running[1] || running[2]; }
void disc_connected(void) {
#ifdef CONFIG_CASEBACK_OPTICAL_PROFILE
  atomic_set(&profile_radio, 1);
#endif
  atomic_clear(&seq);
}
static void poll_fn(struct k_work *unused);
static K_WORK_DELAYABLE_DEFINE(poll_work, poll_fn);

/* The CONTROL worker and poll worker run on the same system workqueue. */
static int afe_write(uint8_t reg, uint8_t val) {
  uint8_t cmd[] = {reg, 0, val};
  const struct spi_buf b = {cmd, sizeof(cmd)};
  const struct spi_buf_set s = {&b, 1};
  return spi_write_dt(&afe, &s);
}

static int afe_read(uint8_t reg, uint8_t *dst, size_t n) {
  uint8_t head[] = {reg, CASEBACK_AFE_SPI_CMD_READ};
  const struct spi_buf tx[] = {{head, 2}, {NULL, n}},
                       rx[] = {{NULL, 2}, {dst, n}};
  const struct spi_buf_set t = {tx, 2}, r = {rx, 2};
  return spi_transceive_dt(&afe, &t, &r);
}

static int imu_rate(int hz) {
  const struct sensor_value rate = {.val1 = hz};
  return sensor_attr_set(imu, SENSOR_CHAN_ACCEL_XYZ,
                         SENSOR_ATTR_SAMPLING_FREQUENCY, &rate);
}

static int temp_power(bool on) {
  uint8_t raw[2], data[3] = {1};
  if (i2c_burst_read(bus, 0x48, 1, raw, sizeof(raw))) return -EIO;
  uint16_t old = sys_get_be16(raw);
  uint16_t mode = (old & ~0x0c00) | (on ? 0 : 0x0400);
  if (old == mode) return 0;
  sys_put_be16(mode, data + 1);
  return i2c_write(bus, data, sizeof(data), 0x48);
}

int disc_dock_level(void) { return valid_gpio ? gpio_pin_get_dt(&dock) : -EIO; }

void disc_poweroff(bool wake_high) {
  if (spi_is_ready_dt(&afe)) (void)afe_write(0x0d, 0x0a);
  if (device_is_ready(bus)) {
    (void)i2c_reg_write_byte(bus, 0x68, 0x7d, 0); /* AUX, gyro, accel, temp off */
    k_msleep(2);
    (void)i2c_reg_write_byte(bus, 0x68, 0x7c, 1); /* advanced power save */
    (void)temp_power(false);
  }
  if (valid_gpio) {
    (void)gpio_pin_configure(charge.port, charge.pin, GPIO_DISCONNECTED);
    (void)gpio_pin_configure(fault.port, fault.pin, GPIO_DISCONNECTED);
  }
  if (valid_gpio && !gpio_pin_interrupt_configure_dt(&dock,
      wake_high ? GPIO_INT_LEVEL_ACTIVE : GPIO_INT_LEVEL_INACTIVE))
    sys_poweroff();
  /* No advertising or logging on a failed wake configuration. */
  k_msleep(1000);
  sys_reboot(SYS_REBOOT_COLD);
}

uint32_t disc_init(void) {
  uint8_t id, tid[2];
  const struct sensor_value range = {.val1 = 4};
  valid_boot = sys_csrand_get(&boot_id, sizeof(boot_id)) == 0;
  valid_gpio = gpio_is_ready_dt(&dock) && gpio_is_ready_dt(&charge) &&
               gpio_is_ready_dt(&fault) &&
               !gpio_pin_configure_dt(&dock, GPIO_INPUT) &&
               !gpio_pin_configure_dt(&charge, GPIO_INPUT) &&
               !gpio_pin_configure_dt(&fault, GPIO_INPUT);
  valid_adc =
      adc_is_ready_dt(&battery_adc) && !adc_channel_setup_dt(&battery_adc);
  if (spi_is_ready_dt(&afe) && !afe_read(0xff, &id, 1) &&
      id == CASEBACK_AFE_PART_ID_MAX86141 && !afe_write(0x0d, 0x0a))
    caps |= CASEBACK_CAP_PPG_RAW;
  if (device_is_ready(imu) &&
      !sensor_attr_set(imu, SENSOR_CHAN_ACCEL_XYZ, SENSOR_ATTR_FULL_SCALE,
                       &range) &&
      !imu_rate(0))
    caps |= CASEBACK_CAP_ACCEL;
  valid_temp = device_is_ready(bus) &&
               !i2c_burst_read(bus, 0x48, 0x0f, tid, 2) &&
               (sys_get_be16(tid) & 0xfff) == 0x117 && !temp_power(true);
  if (valid_temp)
    caps |= CASEBACK_CAP_TEMPERATURE;
  return valid_boot ? caps
                    : caps & ~(CASEBACK_CAP_ACCEL | CASEBACK_CAP_PPG_RAW);
}

uint32_t disc_start_history(void) {
  return valid_boot && valid_gpio && (caps & CASEBACK_CAP_ACCEL) &&
         disc_history_init(boot_id) ? CASEBACK_CAP_IBI_LOG : 0;
}

/* Sample at 1 Hz; the BMI270 runs at 3.125 Hz between observations. */
bool disc_history_sample(int16_t axes[3]) {
  int docked = gpio_pin_get_dt(&dock);
  if ((!IS_ENABLED(CONFIG_CASEBACK_OPTICAL_PROFILE) && !disc_bond_count()) ||
      docked != 0 || running[1] || running[2]) {
    if (history_imu && !running[2] && imu_rate(0))
      return false;
    history_imu = false;
    return false;
  }
  if (!history_imu) {
    history_imu = imu_rate(4) == 0;
    return false;
  }
  uint8_t status, data[6];
  if (i2c_reg_read_byte(bus, 0x68, 0x03, &status) || !(status & 0x80) ||
      i2c_burst_read(bus, 0x68, 0x0c, data, sizeof(data)))
    return false;
  for (unsigned i = 0; i < 3; ++i)
    axes[i] = (int16_t)sys_get_le16(data + 2 * i);
  return true;
}

static ssize_t temperature(struct bt_conn *conn,
                           const struct bt_gatt_attr *attr, void *buf,
                           uint16_t len, uint16_t off) {
  uint8_t raw[2];
  if (!valid_temp || i2c_burst_read(bus, 0x48, 0, raw, 2) ||
      sys_get_be16(raw) == 0x8000)
    return BT_GATT_ERR(BT_ATT_ERR_UNLIKELY);
  int32_t t = (int16_t)sys_get_be16(raw);
  sys_put_le16((uint16_t)((t * 100 + (t >= 0 ? 64 : -64)) / 128), raw);
  return bt_gatt_attr_read(conn, attr, buf, len, off, raw, 2);
}

BT_GATT_SERVICE_DEFINE(
    environment, BT_GATT_PRIMARY_SERVICE(BT_UUID_DECLARE_16(0x181a)),
    BT_GATT_CHARACTERISTIC(BT_UUID_DECLARE_16(0x2a6e), BT_GATT_CHRC_READ,
                           BT_GATT_PERM_READ_ENCRYPT, temperature, NULL, NULL));

static void count_bond(const struct bt_bond_info *info, void *arg) {
  (*(unsigned *)arg)++;
}
unsigned disc_bond_count(void) {
  unsigned bonds = 0;
  bt_foreach_bond(BT_ID_DEFAULT, count_bond, &bonds);
  return bonds;
}
#ifdef CONFIG_BT_SMP_APP_PAIRING_ACCEPT
static enum bt_security_err
accept_pair(struct bt_conn *conn, const struct bt_conn_pairing_feat *feat) {
  return !factory_pending() && disc_dock_level() == 1 && !disc_bond_count()
             ? BT_SECURITY_ERR_SUCCESS
             : BT_SECURITY_ERR_PAIR_NOT_ALLOWED;
}
static const struct bt_conn_auth_cb auth = {.pairing_accept = accept_pair};
#endif

int disc_security_init(void) {
#ifdef CONFIG_BT_SMP_APP_PAIRING_ACCEPT
  return bt_conn_auth_cb_register(&auth);
#else
  return 0;
#endif
}

static int battery(uint8_t *p, size_t *n) {
  int16_t sample;
  struct adc_sequence sq = {.buffer = &sample, .buffer_size = sizeof(sample)};
  if (!valid_adc || !valid_gpio || adc_sequence_init_dt(&battery_adc, &sq) ||
      adc_read_dt(&battery_adc, &sq))
    return CASEBACK_ERR_BAD_STATE;
  int32_t mv = sample;
  int d = gpio_pin_get_dt(&dock), c = gpio_pin_get_dt(&charge),
      f = gpio_pin_get_dt(&fault);
  struct caseback_battery b;
  if (adc_raw_to_millivolts_dt(&battery_adc, &mv) ||
      bench_battery(mv, d, c, f, &b))
    return CASEBACK_ERR_BAD_STATE;
  return caseback_encode_battery(&b, p, CASEBACK_MAX_PAYLOAD, n);
}

static void stop(unsigned id) {
  if (id == 1)
    (void)afe_write(0x0d, 0x0a);
  else if (id == 2)
    (void)imu_rate(0);
  running[id] = false;
}

static inline __attribute__((always_inline)) int afe_green_start(void) {
  /* Rev.5: LED1 (two green emitters), 32 x 0.12 mA, 50.027 Hz, PPG1 only.
       */
  return afe_write(0x0d, 0x0a) || afe_write(0x20, 1) || afe_write(0x21, 0) ||
         afe_write(0x22, 0) || afe_write(0x2a, 0) || afe_write(0x23, 32) ||
         afe_write(0x15, 0x11) || afe_write(0x12, 0x08) ||
         afe_write(0x0a, 0x10) || afe_write(0x0d, 0x08);
}

static int stream(struct bt_conn *conn, const uint8_t *p) {
#ifdef CONFIG_CASEBACK_OPTICAL_PROFILE
  if (profile_is_active()) return CASEBACK_ERR_BAD_STATE;
#endif
  unsigned id = p[0];
  if (id != 1 && id != 2)
    return CASEBACK_ERR_NO_SUCH_STREAM;
  if (p[1] > 1 || p[2] > 1 ||
      !(caps & (id == 1 ? CASEBACK_CAP_PPG_RAW : CASEBACK_CAP_ACCEL)))
    return CASEBACK_ERR_UNSUPPORTED;
  if (!p[1]) {
    if (running[id])
      stop(id);
    return 0;
  }
  if (!valid_boot || bt_gatt_get_mtu(conn) < 40 || (owner && owner != conn))
    return CASEBACK_ERR_BAD_STATE;
  if (!running[id]) {
    int rc;
    if (id == 1) {
      rc = afe_green_start();
    } else {
      history_imu = false;
      last_acc = 0;
      rc = imu_rate(50);
    }
    if (rc) {
      stop(id);
      return CASEBACK_ERR_BAD_STATE;
    }
    gap[id] = false;
  }
  if (!owner)
    owner = bt_conn_ref(conn);
  if (!running[1] && !running[2]) {
    active_interval = true;
    (void)bt_conn_le_param_update(conn, BT_LE_CONN_PARAM(12, 24, 0, 600));
  }
  expires[id] = k_uptime_get() + 600000;
  running[id] = true;
  k_work_reschedule(&poll_work, K_MSEC(15));
  return 0;
}

int disc_control(struct bt_conn *conn, const struct caseback_info *info,
                 const uint8_t *in, size_t len, uint64_t received_ms,
                 uint8_t *out, size_t cap, size_t *out_n) {
  struct caseback_frame f;
  uint8_t p[CASEBACK_MAX_PAYLOAD];
  size_t n = 0;
  if (caseback_decode_frame(in, len, &f) ||
      (f.msg_type != CASEBACK_MSG_BATTERY &&
       f.msg_type != CASEBACK_MSG_TIME_ANCHOR &&
       f.msg_type != CASEBACK_MSG_HISTORY_QUERY &&
       f.msg_type != CASEBACK_MSG_HISTORY_ACK &&
       f.msg_type != CASEBACK_MSG_STREAM_CONTROL))
    return caseback_handle_control(info, in, len, out, cap, out_n);
  int rc = CASEBACK_ERR_BAD_PAYLOAD_LENGTH;
  if (f.msg_type == CASEBACK_MSG_HISTORY_QUERY || f.msg_type == CASEBACK_MSG_HISTORY_ACK) {
    rc = disc_history_request(conn, &f, p, &n);
    if (!rc && f.msg_type == CASEBACK_MSG_HISTORY_ACK) {
      *out_n = 0;
      return 0;
    }
  } else if (f.msg_type == CASEBACK_MSG_TIME_ANCHOR && f.payload_len == 8) {
    last_utc = sys_get_le64(f.payload);
    const struct caseback_time_anchor_reply t = {boot_id, received_ms};
    rc = valid_boot ? caseback_encode_time_anchor_reply(&t, p, sizeof(p), &n)
                    : CASEBACK_ERR_BAD_STATE;
  } else if (f.msg_type == CASEBACK_MSG_STREAM_CONTROL && f.payload_len == 3) {
    rc = stream(conn, f.payload);
    memcpy(p, f.payload, 3);
    p[2] = 1;
    n = 3;
  } else if (f.msg_type == CASEBACK_MSG_BATTERY && !f.payload_len)
    rc = battery(p, &n);
  if (rc) {
    struct caseback_error_msg err = {rc, f.msg_type, 0};
    if (caseback_encode_error(&err, p, sizeof(p), &n))
      return CASEBACK_ERR_INTERNAL;
    f.msg_type = CASEBACK_MSG_ERROR;
  }
  return caseback_encode_frame(f.msg_type, p, n, out, cap, out_n);
}

static void send_sample(uint8_t id, uint8_t *p, size_t len, int64_t time,
                        uint8_t count) {
  uint8_t frame[CASEBACK_MAX_FRAME];
  size_t n;
  sys_put_le16(disc_sequence(), p);
  sys_put_le32(boot_id, p + 2);
  sys_put_le64(time, p + 6);
  p[14] = id;
  p[15] = 1;
  p[16] = gap[id] ? 2 : 0;
  sys_put_le16(500, p + 17);
  p[19] = count;
  gap[id] = caseback_encode_frame(CASEBACK_MSG_STREAM_DATA, p, len, frame,
                                  sizeof(frame), &n) ||
            disc_notify(owner, frame, n);
  if (!gap[id]) disc_sequence_sent();
}

static void poll_fn(struct k_work *unused) {
  struct bt_conn_info info;
  if (!owner)
    return;
  bool linked =
      !bt_conn_get_info(owner, &info) && info.state == BT_CONN_STATE_CONNECTED;
  int64_t now = k_uptime_get();
  for (int i = 1; i <= 2; i++)
    if (running[i] && (!linked || now >= expires[i]))
      stop(i);
  /* Keep the reference only until the last worker has observed a disconnect.
   * A stopped stream on the same link resumes its sequence counter. */
  if (!linked) {
    bt_conn_unref(owner);
    owner = NULL;
    active_interval = false;
    return;
  }
  if (running[1]) {
    uint8_t count = 0, ovf = 0, raw[48], p[68];
    unsigned got = 0;
    if (afe_read(6, &ovf, 1) || afe_read(7, &count, 1))
      gap[1] = true;
    else if (ovf || count > 16) {
      (void)afe_write(0x0a, 0x10);
      gap[1] = true;
    } else if (count && afe_read(8, raw, count * 3))
      gap[1] = true;
    else {
      got = bench_green(raw, count, p + 20, sizeof(p) - 20);
      if (got)
        send_sample(1, p, 20 + 3 * got, now - (int64_t)(20U * (got - 1)), got);
    }
  }
  if (running[2]) {
    uint8_t status, p[26];
    if (i2c_reg_read_byte(bus, 0x68, 0x03, &status))
      gap[2] = true;
    else if (status & 0x80) {
      if (i2c_burst_read(bus, 0x68, 0x0c, p + 20, 6))
        gap[2] = true;
      else {
        if (last_acc && now - last_acc > 35)
          gap[2] = true;
        last_acc = now;
        send_sample(2, p, 26, now, 1);
      }
    }
  }
  if (running[1] || running[2])
    k_work_reschedule(&poll_work, K_MSEC(10));
  else if (active_interval) {
    active_interval = false;
    (void)bt_conn_le_param_update(
        owner, BT_LE_CONN_PARAM(CASEBACK_CONN_INTERVAL_MIN_MS * 4 / 5,
                                CASEBACK_CONN_INTERVAL_MAX_MS * 4 / 5,
                                CASEBACK_CONN_LATENCY,
                                CASEBACK_CONN_SUPERVISION_TIMEOUT_MS / 10));
  }
}

void disc_disconnected(void) {
#ifdef CONFIG_CASEBACK_OPTICAL_PROFILE
  atomic_clear(&profile_radio);
#endif
  k_work_reschedule(&poll_work, K_NO_WAIT);
}

/* SWD acceptance fixture. Word 0 is the request/status, 1..8 are counts,
 * 9..16 are mean ADC codes. No radio command can trigger this operation. */
volatile uint32_t caseback_optical_fixture[17];
#define OPT_REQUEST 0x43424658U

static void fixture_work_fn(struct k_work *work) {
  uint32_t bins[8] = {0}, sums[8] = {0};
  if (caseback_optical_fixture[0] != OPT_REQUEST)
    return;
  caseback_optical_fixture[0] = 1;
  for (unsigned i = 1; i < 17; i++)
    caseback_optical_fixture[i] = 0;
  if (!valid_gpio || gpio_pin_get_dt(&dock) != 1 || owner || running[1] ||
      running[2] || !(caps & CASEBACK_CAP_PPG_RAW)) {
    caseback_optical_fixture[0] = 0xe1;
    return;
  }
  /* Slot 1 green, 2 red, 3 infrared, 4 direct ambient. Both PDs enabled.
   * Initial PDBIAS range 0..65 pF on each detector (SFH7072 nominal 11/55 pF). */
  bool ioerr =
      afe_write(0x0d, 2) || afe_write(0x15, 0x11) || afe_write(0x20, 0x21) ||
      afe_write(0x21, 0x93) || afe_write(0x22, 0) || afe_write(0x2a, 0) ||
      afe_write(0x23, 32) || afe_write(0x24, 32) || afe_write(0x25, 32) ||
      afe_write(0x12, 0x08) || afe_write(0x0a, 0x10) || afe_write(0x0d, 0);
  unsigned complete = 0;
  int64_t deadline = k_uptime_get() + 1000;
  while (!ioerr && complete < 8 && k_uptime_get() < deadline) {
    uint8_t n, ovf, raw[48];
    k_msleep(10);
    if (gpio_pin_get_dt(&dock) != 1 || afe_read(6, &ovf, 1) || ovf ||
        afe_read(7, &n, 1)) {
      ioerr = true;
      break;
    }
    n = MIN(n, 16);
    if (n && afe_read(8, raw, 3 * n)) {
      ioerr = true;
      break;
    }
    for (unsigned i = 0; i < n; i++) {
      uint32_t w = sys_get_be24(raw + 3 * i);
      unsigned tag = w >> 19;
      if (!((tag >= 1 && tag <= 4) || (tag >= 7 && tag <= 10)))
        continue;
      unsigned bin = tag < 7 ? tag - 1 : tag - 3;
      if (bins[bin] < 12) {
        sums[bin] += w & 0x7ffff;
        if (++bins[bin] == 12)
          ++complete;
      }
    }
  }
  /* Always attempt shutdown even after a failed transaction. */
  int off = afe_write(0x0d, 0x0a);
  for (unsigned i = 0; i < 8; i++) {
    caseback_optical_fixture[1 + i] = bins[i];
    caseback_optical_fixture[9 + i] = bins[i] ? sums[i] / bins[i] : 0;
  }
  caseback_optical_fixture[0] = (ioerr || off)  ? 0xe2
                                : complete == 8 ? 2
                                                : 0xe3;
}
static K_WORK_DEFINE(fixture_work, fixture_work_fn);
void disc_check_fixture(void) {
#ifdef CONFIG_CASEBACK_OPTICAL_PROFILE
  profile_check_request();
#endif
  if (caseback_optical_fixture[0] == OPT_REQUEST)
    k_work_submit(&fixture_work);
}


#ifdef CONFIG_CASEBACK_OPTICAL_PROFILE
bool profile_permitted(void) {
  return valid_gpio && !atomic_get(&profile_radio) && !disc_streaming() &&
         (caps & CASEBACK_CAP_PPG_RAW) && gpio_pin_get_dt(&dock) == 0 &&
         gpio_pin_get_dt(&fault) == 0 && caseback_optical_fixture[0] != OPT_REQUEST;
}
bool profile_led(bool enable) {
  uint8_t reg;
  if (enable)
    return afe_green_start() == 0;
  return !afe_write(0x0d, 0x0a) && !afe_read(0x0d, &reg, 1) && (reg & 2);
}
int profile_green(uint8_t samples[48]) {
  uint8_t count = 0, overflow = 0, fifo[48];
  if (afe_read(6, &overflow, 1) || afe_read(7, &count, 1) || overflow ||
      count > 16 || (count && afe_read(8, fifo, count * 3)))
    return -EIO;
  return bench_green(fifo, count, samples, 48);
}
#endif
