#include "bench_data.h"

int bench_battery(int32_t mv, int dock, int charging_pin, int fault_pin,
                  struct caseback_battery *out) {
  if (!out || mv < 0 || mv > 2400 || dock < 0 || charging_pin < 0 ||
      fault_pin < 0)
    return CASEBACK_ERR_BAD_STATE;
  out->voltage_mv = (uint16_t)((mv * 7 + 1) / 3);
  out->percent = CASEBACK_PERCENT_UNKNOWN;
  for (int i = 0; i < 4; i++)
    out->avg_current_ua[i] = CASEBACK_CURRENT_UNKNOWN;
  out->charging = !dock          ? CASEBACK_CHARGING_NOT_CHARGING
                  : fault_pin    ? CASEBACK_CHARGING_FAULT
                  : charging_pin ? CASEBACK_CHARGING_CHARGING
                                 : CASEBACK_CHARGING_UNKNOWN;
  return 0;
}

size_t bench_green(const uint8_t *fifo, size_t words, uint8_t *out,
                   size_t cap) {
  size_t n = 0;
  if (!fifo || !out)
    return 0;
  for (size_t i = 0; i < words; i++, fifo += 3) {
    if (fifo[0] >> 3 != 1)
      continue;
    if (cap - n < 3)
      break;
    out[n++] = fifo[2];
    out[n++] = fifo[1];
    out[n++] = fifo[0] & 7;
  }
  return n / 3;
}
