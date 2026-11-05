#include "bench_data.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void) {
  struct caseback_battery b;
  for (int f = 0; f < 2; f++)
    for (int c = 0; c < 2; c++) {
      assert(!bench_battery(1800, 0, c, f, &b) && b.voltage_mv == 4200 &&
             b.charging == 0);
      assert(!bench_battery(1500, 1, c, f, &b) && b.voltage_mv == 3500);
      assert(b.charging == (f ? 3 : c ? 1 : 255) && b.percent == 255);
      for (int i = 0; i < 4; i++)
        assert(b.avg_current_ua[i] == 65535);
    }
  assert(bench_battery(-1, 1, 0, 0, &b) && bench_battery(2401, 1, 0, 0, &b));
  assert(bench_battery(1200, -1, 0, 0, &b) &&
         bench_battery(1200, 1, -1, 0, &b) &&
         bench_battery(1200, 1, 0, -1, &b));
  const uint8_t raw[] = {0x38, 0, 9, 0x09, 0, 0, 0xf8, 0, 0, 0x0f, 0xff, 0xff};
  const uint8_t expected[] = {0, 0, 1, 255, 255, 7};
  uint8_t out[7] = {0};
  out[6] = 0x42;
  for (size_t cap = 0; cap <= 6; cap++) {
    assert(bench_green(raw, 4, out, cap) == cap / 3);
    assert(!memcmp(out, expected, 3 * (cap / 3)) && out[6] == 0x42);
  }
  puts(
      "bench data: charge/fault, ADC bounds and both optical FIFO tags passed");
}
