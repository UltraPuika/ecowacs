#!/usr/bin/env python3
"""Generate Latvian announcement clips with Piper, then convert them to a target format.

The robot's real audio format is NOT known yet (see RESEARCH.md). So the target
format has no defaults: you must pass --rate, --channels and --sample-format,
copied from `check_audio_format.py` run on an ORIGINAL clip.

Requirements: Python 3.9+, `pip install piper-tts`, ffmpeg, and the Latvian voice
(download lv_LV-aivars-medium.onnx and .onnx.json from the Piper voices page).

Example:
    python3 scripts/generate_latvian_tts.py \\
        --model voices/lv_LV-aivars-medium.onnx --outdir audio/latvian \\
        --rate 16000 --channels 1 --sample-format s16 --ext wav
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

SAFE_ID = re.compile(r"^[a-z0-9_]{1,64}$")
SAMPLE_FORMATS = {"u8", "s16", "s32", "flt"}  # ffmpeg sample_fmt values for PCM output
DEFAULT_PIPER = f"{shlex.quote(sys.executable)} -m piper"


def load_phrases(path: Path) -> list[dict[str, str]]:
    phrases = json.loads(path.read_text(encoding="utf-8"))
    seen: set[str] = set()
    for item in phrases:
        if not SAFE_ID.match(item.get("id", "")) or not item.get("text", "").strip():
            raise SystemExit(f"Invalid phrase entry: {item!r}")
        if item["id"] in seen:
            raise SystemExit(f"Duplicate id: {item['id']}")
        seen.add(item["id"])
    return phrases


def synthesize(piper_cmd: list[str], model: Path, text: str, out: Path) -> None:
    subprocess.run(
        [*piper_cmd, "-m", str(model), "-f", str(out)],
        input=text.encode("utf-8"), check=True, capture_output=True,
    )


def convert(src: Path, dst: Path, rate: int, channels: int, fmt: str, loudness: float | None) -> None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    if loudness is not None:
        cmd += ["-af", f"loudnorm=I={loudness}:TP=-2:LRA=7"]
    cmd += ["-ar", str(rate), "-ac", str(channels), "-sample_fmt", fmt, str(dst)]
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    here = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True, type=Path, help="Piper .onnx voice (lv_LV-aivars-medium)")
    p.add_argument("--phrases", type=Path, default=here / "audio" / "phrases_lv.json")
    p.add_argument("--outdir", type=Path, default=here / "audio" / "latvian")
    p.add_argument("--rate", required=True, type=int, help="Sample rate of the ORIGINAL clips, in Hz")
    p.add_argument("--channels", required=True, type=int, choices=[1, 2])
    p.add_argument("--sample-format", required=True, choices=sorted(SAMPLE_FORMATS))
    p.add_argument("--ext", default="wav", help="Output extension/container (default wav)")
    p.add_argument("--loudness", type=float, default=None,
                   help="Optional loudnorm target in LUFS, e.g. -18. Match the original clips' loudness.")
    p.add_argument("--piper-cmd", default=DEFAULT_PIPER, help="Command that runs Piper")
    args = p.parse_args()

    if not args.model.is_file():
        raise SystemExit(f"Voice model not found: {args.model}")
    if not re.fullmatch(r"[a-z0-9]{2,5}", args.ext):
        raise SystemExit("Invalid --ext")

    args.outdir.mkdir(parents=True, exist_ok=True)
    piper_cmd = shlex.split(args.piper_cmd)
    for item in load_phrases(args.phrases):
        out = args.outdir / f"{item['id']}.{args.ext}"
        if out.exists():
            raise SystemExit(f"Refusing to overwrite {out}. Move or delete it first.")
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.wav"
            synthesize(piper_cmd, args.model, item["text"], raw)
            convert(raw, out, args.rate, args.channels, args.sample_format, args.loudness)
        print(f"{out.name}: {item['text']}")
    return 0


def run() -> int:
    try:
        return main()
    except FileNotFoundError as err:
        raise SystemExit(f"Required program not found: {err.filename}. Install Piper and ffmpeg.") from err
    except subprocess.CalledProcessError as err:
        detail = (err.stderr or b"").decode("utf-8", "replace").strip()[-600:]
        raise SystemExit(f"{err.cmd[0]} failed (exit {err.returncode}).\n{detail}") from err


if __name__ == "__main__":
    raise SystemExit(run())
