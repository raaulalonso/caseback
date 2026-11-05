#pragma once
#include "device.h"
#include <zephyr/bluetooth/conn.h>

uint32_t disc_init(void);
int disc_security_init(void);
uint32_t disc_start_history(void);
int disc_control(struct bt_conn *conn, const struct caseback_info *info,
                 const uint8_t *in, size_t n, uint64_t received_ms,
                 uint8_t *out, size_t cap, size_t *out_n);
int disc_notify(struct bt_conn *conn, const uint8_t *bytes, size_t n);

void disc_connected(void);
void disc_disconnected(void);
void disc_check_fixture(void);
