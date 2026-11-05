# Caseback firmware

The disc and the nRF52840 DK have distinct pin assignments and build targets. Use
a Zephyr 4.2.1 workspace with the matching modules, the Zephyr SDK 0.17.4 ARM toolchain
and west. Set `CASEBACK_FW` to this application directory and run from the workspace:

```sh
west build -p always -b caseback_disc -d build-disc "$CASEBACK_FW" -- -DEXTRA_CONF_FILE=prj_production.conf
west build -p always -b nrf52840dk/nrf52840 -d build-dk "$CASEBACK_FW"
```

On the disc, the first bond requires a powered dock. Recorded 30-second activity
windows carry a boot identifier and history cursor. A bonded phone can retrieve
them later and acknowledge them after local storage succeeds. The acquisition code
sends live optical and motion samples while streaming is active.

Run the portable tests without a board from this directory:

```sh
cc -std=c99 -Wall -Wextra -Werror -Iinclude tests/test_protocol.c src/protocol.c -o /tmp/caseback_protocol_test
/tmp/caseback_protocol_test ../../caseback-protocol/fixtures/golden
cc -std=c99 -Wall -Wextra -Werror -Iinclude tests/test_device.c src/device.c src/protocol.c -o /tmp/caseback_device_test
/tmp/caseback_device_test
```
