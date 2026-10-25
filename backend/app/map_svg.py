"""Display-only processing of the map SVG that deebot-client renders.

When the robot sends a pixel map, deebot-client embeds it in the SVG as an
indexed PNG. Palette index 3 is "Carpet" (``src/map/background_image.rs``).
To hide carpets **in this app's display only**, we copy the floor colour
(index 1) into palette slot 3. Pixel data is untouched and nothing is sent to
the robot. When the SVG has no pixel layer (MapInfo_V2 vector maps), there
are no carpet pixels to hide, and we report that honestly.
"""

from __future__ import annotations

import base64
import binascii
import re
import struct
import zlib
from dataclasses import dataclass

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CARPET_INDEX = 3
FLOOR_INDEX = 1
_DATA_URI = re.compile(rb"data:image/png;base64,([A-Za-z0-9+/=]+)")


@dataclass(frozen=True)
class MapRender:
    """Processed map."""

    svg: bytes
    has_pixel_layer: bool
    carpet_found: bool | None  # None: cannot tell (no indexed pixel layer)


def _iter_chunks(png: bytes) -> list[tuple[bytes, bytes]]:
    if not png.startswith(PNG_SIGNATURE):
        raise ValueError("Not a PNG")
    chunks = []
    pos = len(PNG_SIGNATURE)
    while pos + 8 <= len(png):
        (length,) = struct.unpack(">I", png[pos : pos + 4])
        ctype = png[pos + 4 : pos + 8]
        body = png[pos + 8 : pos + 8 + length]
        if len(body) != length:
            raise ValueError("Truncated PNG")
        chunks.append((ctype, body))
        pos += 12 + length
        if ctype == b"IEND":
            break
    return chunks


def _build_png(chunks: list[tuple[bytes, bytes]]) -> bytes:
    out = bytearray(PNG_SIGNATURE)
    for ctype, body in chunks:
        out += struct.pack(">I", len(body)) + ctype + body
        out += struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF)
    return bytes(out)


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter_rows(raw: bytes, width: int, height: int) -> list[bytes]:
    """Undo PNG filtering for 8-bit, 1 byte-per-pixel images."""
    rows: list[bytes] = []
    prev = bytearray(width)
    stride = width + 1
    for y in range(height):
        start = y * stride
        ftype = raw[start]
        line = bytearray(raw[start + 1 : start + stride])
        if ftype == 1:
            for x in range(1, width):
                line[x] = (line[x] + line[x - 1]) & 0xFF
        elif ftype == 2:
            for x in range(width):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif ftype == 3:
            for x in range(width):
                left = line[x - 1] if x else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 0xFF
        elif ftype == 4:
            for x in range(width):
                left = line[x - 1] if x else 0
                up_left = prev[x - 1] if x else 0
                line[x] = (line[x] + _paeth(left, prev[x], up_left)) & 0xFF
        elif ftype != 0:
            raise ValueError("Unknown PNG filter")
        rows.append(bytes(line))
        prev = line
    return rows


def process_png(png: bytes, hide_carpet: bool) -> tuple[bytes, bool | None]:
    """Return (png, carpet_found). Only 8-bit indexed PNGs are analysed."""
    chunks = _iter_chunks(png)
    ihdr = next((body for ctype, body in chunks if ctype == b"IHDR"), None)
    if ihdr is None or len(ihdr) < 13:
        return png, None
    width, height, depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", ihdr[:13])
    if color_type != 3 or depth != 8 or interlace != 0:
        return png, None
    palette = next((body for ctype, body in chunks if ctype == b"PLTE"), b"")
    if len(palette) < (CARPET_INDEX + 1) * 3:
        return png, False

    raw = zlib.decompress(b"".join(body for ctype, body in chunks if ctype == b"IDAT"))
    if len(raw) < height * (width + 1):
        raise ValueError("Truncated image data")
    carpet = bytes([CARPET_INDEX])
    found = any(carpet in row for row in _unfilter_rows(raw, width, height))

    if not (hide_carpet and found):
        return png, found
    floor = palette[FLOOR_INDEX * 3 : FLOOR_INDEX * 3 + 3]
    pos = CARPET_INDEX * 3
    new_palette = palette[:pos] + floor + palette[pos + 3 :]
    new_chunks = [(c, new_palette if c == b"PLTE" else b) for c, b in chunks]
    return _build_png(new_chunks), found


def render_map(svg: bytes, hide_carpet: bool) -> MapRender:
    """Analyse the SVG's pixel layer and optionally hide carpets in it."""
    found_any: bool | None = None
    has_layer = False

    def replace(match: re.Match[bytes]) -> bytes:
        nonlocal found_any, has_layer
        has_layer = True
        try:
            png = base64.b64decode(match.group(1), validate=True)
            new_png, found = process_png(png, hide_carpet)
        except (ValueError, binascii.Error, zlib.error, struct.error):
            return match.group(0)  # leave anything we do not understand untouched
        if found is not None:
            found_any = bool(found_any) or found
        return b"data:image/png;base64," + base64.b64encode(new_png)

    new_svg = _DATA_URI.sub(replace, svg)
    return MapRender(new_svg, has_layer, found_any)


def make_indexed_png(width: int, height: int, pixels: list[list[int]], palette: bytes) -> bytes:
    """Build a small indexed PNG (used by demo mode and tests)."""
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)
    trns = bytes([0] + [255] * (len(palette) // 3 - 1))
    return _build_png(
        [
            (b"IHDR", ihdr),
            (b"PLTE", palette),
            (b"tRNS", trns),
            (b"IDAT", zlib.compress(raw)),
            (b"IEND", b""),
        ]
    )
