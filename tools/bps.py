#!/usr/bin/env python3
"""Create and apply BPS patches (the beat patch format), standard library only.

usage: python3 tools/bps.py make SOURCE TARGET PATCH
       python3 tools/bps.py apply SOURCE PATCH TARGET

make() writes a simple patch: unchanged runs are copied from the source (SourceRead), changed runs
are stored in the patch (TargetRead), except long runs of one byte (an expanded ROM's padding),
stored as one byte and a TargetCopy of it. apply() handles all four actions, and checks the source,
target and patch CRC32s.
"""
import sys, zlib

SOURCE_READ, TARGET_READ, SOURCE_COPY, TARGET_COPY = range(4)


def _num(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def _read_num(b, i):
    data, shift = 0, 1
    while True:
        x = b[i]
        i += 1
        data += (x & 0x7F) * shift
        if x & 0x80:
            return data, i
        shift <<= 7
        data += shift


def make(source, target):
    out = bytearray(b'BPS1' + _num(len(source)) + _num(len(target)) + _num(0))
    i, n = 0, len(target)
    to = 0                                          # TargetCopy's relative offset (see apply)

    def changed(i, j):
        """Store target[i:j]: a long run of one byte (the padding of an expanded ROM) as one
        byte read and a TargetCopy of it; anything else as TargetRead."""
        nonlocal to
        while i < j:
            k = i
            while k < j and k - i < 64 and target[k] == target[i]:
                k += 1
            if k - i == 64:                         # a long run: read its first byte, copy the rest
                while k < j and target[k] == target[i]:
                    k += 1
                out.extend(_num(TARGET_READ) + target[i:i + 1])
                off = i - to
                out.extend(_num(((k - i - 2) << 2) | TARGET_COPY) + _num((abs(off) << 1) | (off < 0)))
                to = i + (k - i - 1)
                i = k
                continue
            k = i
            while k < j and not (k + 64 <= j and target[k:k + 64] == target[k:k + 1] * 64):
                k += 1
            out.extend(_num(((k - i - 1) << 2) | TARGET_READ) + target[i:k])
            i = k

    while i < n:
        same = i < len(source) and source[i] == target[i]
        j = i
        while j < n and (j < len(source) and source[j] == target[j]) == same:
            j += 1
        if same:
            out += _num(((j - i - 1) << 2) | SOURCE_READ)
        else:
            changed(i, j)
        i = j
    out += zlib.crc32(source).to_bytes(4, 'little') + zlib.crc32(target).to_bytes(4, 'little')
    out += zlib.crc32(out).to_bytes(4, 'little')
    return bytes(out)


def apply(source, patch):
    if patch[:4] != b'BPS1':
        raise ValueError('not a BPS patch')
    if zlib.crc32(patch[:-4]) != int.from_bytes(patch[-4:], 'little'):
        raise ValueError('patch CRC mismatch')
    if zlib.crc32(source) != int.from_bytes(patch[-12:-8], 'little'):
        raise ValueError('source CRC mismatch: not the ROM this patch is for')
    i = 4
    ssize, i = _read_num(patch, i)
    tsize, i = _read_num(patch, i)
    msize, i = _read_num(patch, i)
    i += msize
    target = bytearray()
    so = to = 0
    end = len(patch) - 12
    while i < end:
        d, i = _read_num(patch, i)
        cmd, length = d & 3, (d >> 2) + 1
        if cmd == SOURCE_READ:
            target += source[len(target):len(target) + length]
        elif cmd == TARGET_READ:
            target += patch[i:i + length]
            i += length
        else:
            off, i = _read_num(patch, i)
            off = (-1 if off & 1 else 1) * (off >> 1)
            if cmd == SOURCE_COPY:
                so += off
                target += source[so:so + length]
                so += length
            else:
                to += off
                for _ in range(length):
                    target.append(target[to])
                    to += 1
    if len(target) != tsize or zlib.crc32(target) != int.from_bytes(patch[-8:-4], 'little'):
        raise ValueError('target CRC mismatch')
    return bytes(target)


if __name__ == '__main__':
    cmd = sys.argv[1:2]
    if cmd == ['make'] and len(sys.argv) == 5:
        open(sys.argv[4], 'wb').write(make(open(sys.argv[2], 'rb').read(), open(sys.argv[3], 'rb').read()))
    elif cmd == ['apply'] and len(sys.argv) == 5:
        open(sys.argv[4], 'wb').write(apply(open(sys.argv[2], 'rb').read(), open(sys.argv[3], 'rb').read()))
    else:
        sys.exit(__doc__)
