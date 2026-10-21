#!/usr/bin/env python3
"""Find text that is part of pictures (graphics), so it can be counted and redrawn.

usage: python3 tools/pictures.py [--rom FILE] [--sheets] [--pages]

The game's graphics are Huffman-compressed LZ77 data (Gfx_LoadList kinds
10-30: HuffUnComp, then LZ77UnComp), or uncompressed (kinds 0-2, copied straight to VRAM). This
tool:
  - scans the ROM for Huffman headers whose data decodes to a valid LZ77 stream, and decodes them;
  - finds graphics-list entries (struct GfxEntry: source, kind 0-2, VRAM destination, size) for
    the uncompressed ones;
  - counts, in each, the 8x8 tiles whose shape (which pixels are set) is exactly one half of a
    glyph in the game's font: text drawn with the font and stored as a picture;
  - with --sheets, writes every block as a greyscale PNG of its tiles (32 to a row) to
    work/pictures/ (local only: they are the game's graphics), to look for hand-drawn text;
  - with --pages, packs all blocks into work/pictures/page-NN.png (4 columns of 1024-pixel strips
    per page, blocks one after another with an 8-pixel gap) and lists where each block starts in
    work/pictures/pages.tsv, for looking through everything quickly.
Writes work/pictures.tsv (address, kind, size, tiles, font tiles) and prints counts only.
"""
import argparse, os, struct, sys, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gamedata

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM_BASE = 0x08000000
FONT, FONT_WIDE, OFFSETS, WIDE_OFFSETS = 0x087853C0, 0x0878D3C0, 0x081B3CC8, 0x081B3EBC


def huff(rom, a):
    """BIOS HuffUnComp of the data at file offset a; None if it isn't valid."""
    head = struct.unpack_from('<I', rom, a)[0]
    bits, size = head & 15, head >> 8
    if (head >> 4) & 15 != 2 or bits not in (4, 8) or not 32 <= size <= 0x40000:
        return None
    tree = a + 5
    data = a + 4 + (rom[a + 4] + 1) * 2
    tree_end = data
    out, acc, nacc, node = bytearray(), 0, 0, tree
    per_word = 32 // bits
    while len(out) < size:
        if data + 4 > len(rom):
            return None
        word = struct.unpack_from('<I', rom, data)[0]
        data += 4
        for k in range(31, -1, -1):
            b = (word >> k) & 1
            n = rom[node]
            child = (node & ~1) + (n & 0x3F) * 2 + 2 + b
            if child >= tree_end:
                return None
            if n & (0x80 >> b):
                acc |= rom[child] << (bits * nacc)
                nacc += 1
                node = tree
                if nacc == per_word:
                    out += struct.pack('<I', acc & 0xFFFFFFFF)
                    acc = nacc = 0
                    if len(out) >= size:
                        break
            else:
                node = child
    return bytes(out[:size])


def lz77(src):
    """BIOS LZ77UnComp; None if it isn't valid."""
    if len(src) < 4 or src[0] != 0x10:
        return None
    size = struct.unpack_from('<I', src, 0)[0] >> 8
    if not 32 <= size <= 0x40000:
        return None
    out, i = bytearray(), 4
    while len(out) < size:
        if i >= len(src):
            return None
        flags = src[i]
        i += 1
        for k in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> k):
                if i + 1 >= len(src):
                    return None
                n, disp = (src[i] >> 4) + 3, ((src[i] & 15) << 8 | src[i + 1]) + 1
                i += 2
                if disp > len(out):
                    return None
                for _ in range(n):
                    out.append(out[-disp])
            else:
                if i >= len(src):
                    return None
                out.append(src[i])
                i += 1
    return bytes(out[:size])


def mask(tile):
    """Which of a 4-bit tile's 64 pixels are set, as a 64-bit number."""
    m = 0
    for i, b in enumerate(tile):
        if b & 15:
            m |= 1 << (2 * i)
        if b >> 4:
            m |= 1 << (2 * i + 1)
    return m


def font_masks(rom):
    masks = set()
    offs = struct.unpack_from('<250H', rom, OFFSETS - ROM_BASE)
    for o in offs:
        for half in (0, 0x400):
            masks.add(mask(rom[FONT - ROM_BASE + o + half:FONT - ROM_BASE + o + half + 32]))
    wide = struct.unpack_from('<208H', rom, WIDE_OFFSETS - ROM_BASE)
    for o in wide:
        for half in (0, 0x400):
            for col in (0, 32):
                a = FONT_WIDE - ROM_BASE + o + half + col
                masks.add(mask(rom[a:a + 32]))
    return {m for m in masks if bin(m).count('1') >= 6}      # ignore blank and near-blank tiles


def tile_rows(data):
    """The 4-bit tiles in data as greyscale pixel rows, 32 tiles (256 pixels) wide."""
    tiles = len(data) // 32
    w, h = 32 * 8, ((tiles + 31) // 32) * 8
    pix = [[0] * w for _ in range(h)]
    for t in range(tiles):
        tx, ty = (t % 32) * 8, (t // 32) * 8
        for i in range(32):
            b = data[32 * t + i]
            y, x = i // 4, (i % 4) * 2
            pix[ty + y][tx + x] = (b & 15) * 17
            pix[ty + y][tx + x + 1] = (b >> 4) * 17
    return pix


def write_png(path, pix):
    w, h = len(pix[0]), len(pix)
    raw = b''.join(b'\0' + bytes(row) for row in pix)
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0)) +
                           chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def main():
    ap = argparse.ArgumentParser()
    gamedata.add_rom_argument(ap)
    ap.add_argument('--sheets', action='store_true')
    ap.add_argument('--pages', action='store_true')
    opt = ap.parse_args()
    rom = gamedata.read_rom(opt.rom)
    fm = font_masks(rom)

    blocks = []                                   # (address, kind, data)
    for a in range(0, len(rom) - 8, 4):
        if rom[a] not in (0x24, 0x28):
            continue
        h = huff(rom, a)
        d = lz77(h) if h else None
        if d:
            blocks.append((ROM_BASE + a, 'huff+lz77', d))
    # uncompressed graphics-list entries: source in ROM, kind 0-2, VRAM destination, size
    seen = set()
    for a in range(0, len(rom) - 16, 4):
        src, kind, dest, size = struct.unpack_from('<IB3xIH', rom, a)
        if (kind <= 2 and ROM_BASE <= src < ROM_BASE + len(rom) and 0x06000000 <= dest < 0x06018000
                and 32 <= size <= 0x10000 and size % 32 == 0 and src not in seen and src != FONT):
            seen.add(src)
            blocks.append((src, 'copy', rom[src - ROM_BASE:src - ROM_BASE + size]))

    rows = []
    for addr, kind, data in blocks:
        tiles = len(data) // 32
        hits = sum(1 for t in range(tiles) if mask(data[32 * t:32 * t + 32]) in fm)
        rows.append((addr, kind, len(data), tiles, hits))
    os.makedirs(os.path.join(HERE, 'work'), exist_ok=True)
    with open(os.path.join(HERE, 'work', 'pictures.tsv'), 'w') as f:
        f.write('# Graphics blocks in the ROM and their tiles that match font glyphs (local only).\n')
        f.write('address\tkind\tbytes\ttiles\tfont_tiles\n')
        for r in sorted(rows, key=lambda r: -r[4]):
            f.write('0x%08X\t%s\t%d\t%d\t%d\n' % r)
    if opt.sheets:
        d = os.path.join(HERE, 'work', 'pictures')
        os.makedirs(d, exist_ok=True)
        for addr, kind, data in blocks:
            write_png(os.path.join(d, '%08X.png' % addr), tile_rows(data))
    if opt.pages:
        d = os.path.join(HERE, 'work', 'pictures')
        os.makedirs(d, exist_ok=True)
        strip, where = [], []
        for addr, kind, data in sorted(blocks):
            where.append((addr, len(strip)))
            strip += tile_rows(data) + [[0x40] * 256 for _ in range(8)]
        col_h, gap = 1024, 8
        segs = [strip[i:i + col_h] for i in range(0, len(strip), col_h)]
        pages = [segs[i:i + 4] for i in range(0, len(segs), 4)]
        for n, page in enumerate(pages):
            pix = [[0x20] * (4 * 256 + 3 * gap) for _ in range(col_h)]
            for c, seg in enumerate(page):
                for y, row in enumerate(seg):
                    pix[y][c * (256 + gap):c * (256 + gap) + 256] = row
            write_png(os.path.join(d, 'page-%02d.png' % n), pix)
        with open(os.path.join(d, 'pages.tsv'), 'w') as f:
            f.write('address\tpage\tcolumn\ty\n')
            for addr, y in where:
                seg = y // col_h
                f.write('0x%08X\t%d\t%d\t%d\n' % (addr, seg // 4, seg % 4, y % col_h))
        print('work/pictures/page-*.png: %d pages' % len(pages))
    with_text = [r for r in rows if r[4] >= 4]
    print('graphics blocks: %d compressed, %d uncompressed; %d tiles in all' % (
        sum(1 for r in rows if r[1] != 'copy'), sum(1 for r in rows if r[1] == 'copy'), sum(r[3] for r in rows)))
    print('blocks with 4 or more tiles shaped like font glyphs: %d (%d such tiles)' % (len(with_text), sum(r[4] for r in with_text)))
    print('work/pictures.tsv written%s (local only)' % (', and work/pictures/*.png' if opt.sheets else ''))


if __name__ == '__main__':
    main()
