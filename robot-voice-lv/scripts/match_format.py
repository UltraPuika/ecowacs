"""Transcode generated Latvian WAVs to the exact format of the identified originals.

Uses the `original_file` column of voice_map.csv (relative to --originals). Rows
without an identified original are skipped: no guessing of target formats.
Output keeps the original filename so a package can be rebuilt 1:1.

  python scripts/match_format.py --originals audio/original/files --out audio/latvian/matched
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name,sample_rate,channels,sample_fmt,bit_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(r.stdout)["streams"][0]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--map", type=Path, default=ROOT / "voice_map.csv")
    p.add_argument("--latvian", type=Path, default=ROOT / "audio" / "latvian")
    p.add_argument("--originals", type=Path, required=True)
    p.add_argument("--out", type=Path, default=ROOT / "audio" / "latvian" / "matched")
    args = p.parse_args()

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        print("ffmpeg/ffprobe not found on PATH.", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)

    with args.map.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["original_file"].strip()]
    if not rows:
        print("No row in voice_map.csv has original_file set. Identify originals first.")
        return 1

    for row in rows:
        src = args.latvian / f"{row['id']}.wav"
        orig = args.originals / row["original_file"]
        if not src.is_file() or not orig.is_file():
            print(f"skip  {row['id']}: missing {src if not src.is_file() else orig}")
            continue
        s = probe(orig)
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src),
               "-ar", s["sample_rate"], "-ac", str(s["channels"]), "-c:a", s["codec_name"]]
        if s.get("sample_fmt"):
            cmd += ["-sample_fmt", s["sample_fmt"]]
        if s.get("bit_rate") and not s["codec_name"].startswith("pcm_"):
            cmd += ["-b:a", s["bit_rate"]]
        dst = args.out / Path(row["original_file"]).name
        cmd.append(str(dst))
        subprocess.run(cmd, check=True)
        print(f"ok    {row['id']:<22} -> {dst.name} ({s['codec_name']}, {s['sample_rate']} Hz, {s['channels']}ch)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
