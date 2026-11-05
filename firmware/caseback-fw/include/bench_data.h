#pragma once
#include "protocol.h"
#include <stddef.h>
#include <stdint.h>
int bench_battery(int32_t mv, int dock, int charging_pin, int fault_pin,
                  struct caseback_battery *out);
size_t bench_green(const uint8_t *fifo, size_t words, uint8_t *out, size_t cap);
