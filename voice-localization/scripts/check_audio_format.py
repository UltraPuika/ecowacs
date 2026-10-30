#!/usr/bin/env python3
"""Describe audio files with ffprobe, or compare Latvian clips against an original.

    python3 scripts/check_audio_format.py audio/original/some_clip.ogg
    python3 scripts/check_audio_format.py --compare audio/original/some_clip.ogg audio/latvian/stuck.ogg

Compares codec, sample rate, channels, sample format and container. Duration and
loudness are reported but only flagged when they differ by more than 3x / 6 LU.
Exit status 1 means the formats differ.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def probe(path: Path) -> dict[str, object]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    stream = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    if stream is None:
        raise SystemExit(f"{path}: no audio stream")
    return {
        "container": data["format"].get("format_name"),
        "codec": stream.get("codec_name"),
        "sample_rate": int(stream.get("sample_rate", 0)),
        "channels": int(stream.get("channels", 0)),
        "sample_format": stream.get("sample_fmt"),
        "bit_rate": int(stream.get("bit_rate") or data["format"].get("bit_rate") or 0),
        "duration_s": round(float(data["format"].get("duration", 0)), 2),
    }


def loudness(path: Path) -> float | None:
    run = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    found = re.findall(r"I:\s+(-?\d+\.\d+) LUFS", run.stderr)
    return float(found[-1]) if found else None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--compare", action="store_true", help="two files: original, candidate")
    p.add_argument("files", nargs="+", type=Path)
    args = p.parse_args()

    if not args.compare:
        for f in args.files:
            info = probe(f) | {"loudness_lufs": loudness(f)}
            print(f"{f}: {json.dumps(info)}")
        return 0

    if len(args.files) != 2:
        raise SystemExit("--compare needs exactly two files: original candidate")
    orig, cand = (probe(f) for f in args.files)
    lo, lc = loudness(args.files[0]), loudness(args.files[1])
    problems = [
        f"{k}: original={orig[k]} candidate={cand[k]}"
        for k in ("container", "codec", "sample_rate", "channels", "sample_format")
        if orig[k] != cand[k]
    ]
    if orig["duration_s"] and not (1 / 3 <= cand["duration_s"] / orig["duration_s"] <= 3):  # type: ignore[operator]
        problems.append(f"duration: original={orig['duration_s']}s candidate={cand['duration_s']}s")
    if lo is not None and lc is not None and abs(lo - lc) > 6:
        problems.append(f"loudness: original={lo} LUFS candidate={lc} LUFS")
    print("MATCH" if not problems else "DIFFERENT:\n  " + "\n  ".join(problems))
    return 1 if problems else 0


def run() -> int:
    try:
        return main()
    except FileNotFoundError as err:
        raise SystemExit(f"Required program not found: {err.filename}. Install ffmpeg (includes ffprobe).") from err
    except subprocess.CalledProcessError as err:
        raise SystemExit(f"{err.cmd[-1]}: not readable as audio ({err.cmd[0]} exit {err.returncode}).") from err


if __name__ == "__main__":
    sys.exit(run())
