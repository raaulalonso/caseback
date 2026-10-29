import pytest

from caseback_protocol.crc16 import crc16_ccitt


def test_crc16_ccitt_empty():
    assert crc16_ccitt(b"") == 0xFFFF


def test_crc16_ccitt_known_vector_123456789():
    # CRC-16/CCITT-FALSE check value for "123456789"
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_crc16_ccitt_single_byte():
    assert crc16_ccitt(b"\x00") == 0xE1F0


@pytest.mark.parametrize("data", [b"\xA5", bytes(range(256)), b"\xFF" * 100, b"\xA5\x01\x02\x10\x00"])
def test_crc16_matches_stdlib(data):
    import binascii

    assert crc16_ccitt(data) == binascii.crc_hqx(data, 0xFFFF)
