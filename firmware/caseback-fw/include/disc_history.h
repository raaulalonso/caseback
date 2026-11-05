#pragma once
#include "protocol.h"
#include <zephyr/bluetooth/conn.h>

bool disc_history_init(uint32_t boot);
int disc_history_request(struct bt_conn *conn, const struct caseback_frame *frame,
			 uint8_t *payload, size_t *len);
void disc_history_replied(struct bt_conn *conn, bool success);
bool disc_history_sample(int16_t axes[3]);
uint16_t disc_sequence(void);
void disc_sequence_sent(void);
bool disc_streaming(void);
