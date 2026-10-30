"""Inventory original audio files read-only, or verify a backup against an inventory.

  python scripts/inspect_audio.py SRC_DIR --out audio/original/manifest.json
  python scripts/inspect_audio.py BACKUP_DIR --verify audio/original/manifest.json

Never modifies SRC_DIR. Format detection uses magic bytes; WAV parameters come
from the stdlib; other formats are probed with ffprobe when it is installed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

MAGIC = [
    (b"RIFF", 0, "wav"),
    (b"OggS", 0, "ogg"),
    (b"fLaC", 0, "flac"),
    (b"#!AMR", 0, "amr"),
    (b"ID3", 0, "mp3"),
    (b"\xff\xfb", 0, "mp3"),
    (b"\xff\xf3", 0, "mp3"),
    (b"\xff\xf1", 0, "aac-adts"),
    (b"\xff\xf9", 0, "aac-adts"),
    (b"ftyp", 4, "mp4/m4a"),
    (b"PK\x03\x04", 0, "zip"),
    (b"\x1f\x8b", 0, "gzip"),
    (b"Salted__", 0, "openssl-encrypted"),
]


def sniff(head: bytes) -> str:
    for magic, offset, name in MAGIC:
        if head[offset:offset + len(magic)] == magic:
            return name
    return "unknown"


def describe(path: Path) -> dict:
    data = path.read_bytes()
    info: dict = {
        "file": path.as_posix(),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "detected": sniff(data[:16]),
    }
    if info["detected"] == "wav":
        try:
            with wave.open(str(path), "rb") as wf:
                info.update(sample_rate=wf.getframerate(), channels=wf.getnchannels(),
                            bits=wf.getsampwidth() * 8,
                            duration_s=round(wf.getnframes() / wf.getframerate(), 3))
        except wave.Error as exc:
            info["wav_error"] = str(exc)  # e.g. non-PCM (ADPCM) WAV; ffprobe below covers it
    if shutil.which("ffprobe"):
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_name,sample_rate,channels,bits_per_sample,bit_rate:format=duration:format_tags",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=False,
        )
        if r.returncode == 0:
            info["ffprobe"] = json.loads(r.stdout)
    return info


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("src", type=Path)
    p.add_argument("--out", type=Path, help="Write inventory JSON here")
    p.add_argument("--verify", type=Path, help="Compare src against an existing inventory")
    args = p.parse_args()

    files = sorted(f for f in args.src.rglob("*") if f.is_file())
    entries = [describe(f) | {"file": f.relative_to(args.src).as_posix()} for f in files]

    if args.verify:
        expected = {e["file"]: e["sha256"] for e in json.loads(args.verify.read_text(encoding="utf-8"))["files"]}
        actual = {e["file"]: e["sha256"] for e in entries}
        missing = sorted(expected.keys() - actual.keys())
        changed = sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k])
        for k in missing:
            print(f"MISSING  {k}")
        for k in changed:
            print(f"CHANGED  {k}")
        print(f"{len(expected) - len(missing) - len(changed)}/{len(expected)} files verified")
        return 1 if missing or changed else 0

    for e in entries:
        extra = f"{e.get('sample_rate', '')} Hz {e.get('channels', '')}ch {e.get('bits', '')}bit" if "sample_rate" in e else ""
        print(f"{e['detected']:<18} {e['size']:>9}  {e['file']}  {extra}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"source": str(args.src), "files": entries}, indent=2), encoding="utf-8")
        print(f"inventory written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
