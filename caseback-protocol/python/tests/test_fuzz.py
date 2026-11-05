"""Deterministic mutation tests: the decoder never crashes and CRC failures are detected."""

import random

from caseback_protocol import golden
from caseback_protocol.errors import FrameError
from caseback_protocol.framing import decode_frame

SEED = 0x0F1E2D3C
ROUNDS = 400


def corpus():
    return list(golden.positive_frames().values())


def test_random_mutations_never_crash():
    rng = random.Random(SEED)
    for data in corpus():
        for _ in range(ROUNDS):
            buf = bytearray(data)
            for _ in range(rng.randint(1, 4)):
                op = rng.randrange(4)
                if op == 0 and buf:
                    buf[rng.randrange(len(buf))] = rng.randrange(256)
                elif op == 1 and buf:
                    del buf[rng.randrange(len(buf)) :]
                elif op == 2:
                    buf.extend(rng.randbytes(rng.randint(1, 8)))
                elif buf:
                    buf[rng.randrange(len(buf))] ^= 1 << rng.randrange(8)
            try:
                decode_frame(bytes(buf))
            except FrameError:
                pass


def test_pure_random_bytes_never_crash():
    rng = random.Random(SEED + 1)
    for _ in range(2000):
        try:
            decode_frame(rng.randbytes(rng.randint(0, 200)))
        except FrameError:
            pass


def test_any_single_byte_change_is_detected():
    rng = random.Random(SEED + 2)
    for data in corpus():
        for i in range(len(data)):
            mutated = bytearray(data)
            mutated[i] ^= rng.randrange(1, 256)
            try:
                decode_frame(bytes(mutated))
            except FrameError:
                continue
            raise AssertionError(f"single-byte change at {i} of {data.hex()} not detected")


def test_random_bit_flips_in_body_fail_the_crc():
    # keep header and length valid, flip bits only in the payload: the CRC (Hamming distance >= 4 at
    # these lengths) must catch up to 3 flipped bits
    rng = random.Random(SEED + 3)
    for data in corpus():
        if len(data) <= 9:
            continue
        for _ in range(ROUNDS):
            mutated = bytearray(data)
            for pos in rng.sample(range(5 * 8, (len(data) - 2) * 8), rng.randint(1, 3)):
                mutated[pos // 8] ^= 1 << (pos % 8)
            try:
                decode_frame(bytes(mutated))
            except FrameError as exc:
                assert exc.code.name == "BAD_CRC"
            else:
                raise AssertionError("corrupted payload accepted")
