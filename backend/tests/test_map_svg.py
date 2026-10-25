"""Display-only carpet hiding in the map SVG."""

from __future__ import annotations

import base64
import struct
import zlib

from app.map_svg import _build_png, make_indexed_png, process_png, render_map

PALETTE = bytes([0, 0, 0, 0xBA, 0xDA, 0xFF, 0x4E, 0x96, 0xE2, 0x1A, 0x81, 0xED])


def palette_of(png: bytes) -> bytes:
    pos = png.index(b"PLTE")
    (length,) = struct.unpack(">I", png[pos - 4 : pos])
    return png[pos + 4 : pos + 4 + length]


def test_detects_and_hides_carpet():
    png = make_indexed_png(3, 2, [[1, 3, 2], [1, 1, 1]], PALETTE)
    same, found = process_png(png, hide_carpet=False)
    assert found is True and same == png
    hidden, found = process_png(png, hide_carpet=True)
    assert found is True
    pal = palette_of(hidden)
    assert pal[9:12] == pal[3:6]  # carpet colour == floor colour
    # pixel data is unchanged: only the palette differs
    idat = png[png.index(b"IDAT") :]
    assert hidden.endswith(idat)


def test_no_carpet_pixels():
    png = make_indexed_png(2, 2, [[1, 2], [1, 1]], PALETTE)
    out, found = process_png(png, hide_carpet=True)
    assert found is False and out == png


def test_filtered_rows_are_decoded():
    # Row 0 uses filter 1 (Sub), row 1 uses filter 2 (Up), row 2 uses filter 4 (Paeth)
    rows = [[1, 1, 3], [1, 1, 3], [1, 2, 1]]
    raw = bytearray()
    raw += bytes([1, rows[0][0], 0, 2])  # sub: 1, 1, 3
    raw += bytes([2, 0, 0, 0])  # up: same as previous row
    raw += bytes([4, 0, 1, 255])  # paeth -> 1, 2, 1
    ihdr = struct.pack(">IIBBBBB", 3, 3, 8, 3, 0, 0, 0)
    png = _build_png([(b"IHDR", ihdr), (b"PLTE", PALETTE), (b"IDAT", zlib.compress(bytes(raw))), (b"IEND", b"")])
    _, found = process_png(png, hide_carpet=False)
    assert found is True


def test_non_indexed_png_is_left_alone():
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # truecolour
    png = _build_png([(b"IHDR", ihdr), (b"IDAT", zlib.compress(b"\x00\x01\x02\x03")), (b"IEND", b"")])
    out, found = process_png(png, hide_carpet=True)
    assert found is None and out == png


def test_vector_svg_has_no_pixel_layer():
    render = render_map(b'<svg><path d="M0 0h1"/></svg>', hide_carpet=True)
    assert render.has_pixel_layer is False and render.carpet_found is None


def test_render_map_rewrites_only_png():
    png = make_indexed_png(2, 1, [[1, 3]], PALETTE)
    svg = b'<svg><image href="data:image/png;base64,' + base64.b64encode(png) + b'"/><path d="M1"/></svg>'
    render = render_map(svg, hide_carpet=True)
    assert render.has_pixel_layer and render.carpet_found is True
    assert render.svg.endswith(b'"/><path d="M1"/></svg>')
    assert render.svg != svg


def test_corrupt_png_left_untouched():
    svg = b'<svg><image href="data:image/png;base64,AAAA"/></svg>'
    render = render_map(svg, hide_carpet=True)
    assert render.svg == svg and render.carpet_found is None
