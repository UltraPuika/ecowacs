"""Generate Latvian announcement WAVs from voice_map.csv.

Engines:
  edge    free Microsoft neural voices via edge-tts (lv-LV-NilsNeural male,
          lv-LV-EveritaNeural female); no key, sends the texts to Microsoft
          (24000 Hz mono 16-bit after decoding with bundled ffmpeg)
  piper   local, offline (lv_LV-aivars-medium, 22050 Hz mono 16-bit)
  openai  OpenAI gpt-4o-mini-tts, more natural; needs OPENAI_API_KEY and sends
          only the announcement texts to OpenAI (24000 Hz mono 16-bit)

Output is a staging format only. Use match_format.py to transcode to the robot's
original format once the original files have been identified.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import wave
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OPENAI_URL = "https://api.openai.com/v1/audio/speech"
OPENAI_RATE = 24000  # response_format "pcm" is 24 kHz 16-bit mono little-endian
OPENAI_INSTRUCTIONS = (
    "Speak natural, native Latvian (lv-LV), like a Riga-born speaker. "
    "Stress the first syllable of every word, as in standard Latvian. "
    "Keep long vowels ā, ē, ī, ū clearly long and pronounce č, ģ, ķ, ļ, ņ, š, ž correctly. "
    "Tone: calm, friendly, clear home-appliance announcement. Short pause at commas. "
    "Read exactly the given text; do not add or translate anything."
)


def piper_engine(args: argparse.Namespace) -> Callable[[str, Path], None]:
    from piper import PiperVoice, SynthesisConfig

    if not args.model.is_file():
        sys.exit(f"Model not found: {args.model}\n"
                 "Run: python -m piper.download_voices --download-dir models lv_LV-aivars-medium")
    voice = PiperVoice.load(args.model)
    cfg = SynthesisConfig(length_scale=args.length_scale)

    def synth(text: str, target: Path) -> None:
        with wave.open(str(target), "wb") as wf:
            voice.synthesize_wav(text, wf, syn_config=cfg)

    return synth


def edge_engine(args: argparse.Namespace) -> Callable[[str, Path], None]:
    import edge_tts
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    # Edge pads ~0.5 s of silence at both ends; trim it, keep 50 ms tail.
    trim = ("silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
            "silenceremove=start_periods=1:start_threshold=-50dB,areverse,apad=pad_dur=0.05")

    def synth(text: str, target: Path) -> None:
        mp3 = target.with_suffix(".mp3")
        asyncio.run(edge_tts.Communicate(text, args.edge_voice, rate=args.rate, pitch=args.pitch).save(str(mp3)))
        subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(mp3), "-af", trim, "-ac", "1", "-ar", "24000",
                        "-c:a", "pcm_s16le", str(target)], check=True)
        mp3.unlink()

    return synth


def openai_engine(args: argparse.Namespace) -> Callable[[str, Path], None]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY is not set. In PowerShell: $env:OPENAI_API_KEY = '<your key>'")

    def synth(text: str, target: Path) -> None:
        body = json.dumps({
            "model": args.openai_model,
            "voice": args.voice,
            "input": text,
            "instructions": args.instructions,
            "response_format": "pcm",
            "speed": args.speed,
        }).encode()
        req = urllib.request.Request(OPENAI_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                pcm = resp.read()
        except urllib.error.HTTPError as exc:
            sys.exit(f"OpenAI error {exc.code}: {exc.read().decode(errors='replace')[:500]}")
        with wave.open(str(target), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(OPENAI_RATE)
            wf.writeframes(pcm)

    return synth


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--engine", choices=["edge", "piper", "openai"], default="edge")
    p.add_argument("--map", type=Path, default=ROOT / "voice_map.csv")
    p.add_argument("--out", type=Path, default=ROOT / "audio" / "latvian")
    p.add_argument("--only", nargs="*", help="Generate only these ids")
    p.add_argument("--text-column", default="latvian", help="CSV column with the text, e.g. latvian_female")
    p.add_argument("--include-provisional", action="store_true",
                   help="Also generate rows whose status starts with PROVISIONAL")
    g = p.add_argument_group("edge")
    g.add_argument("--edge-voice", default="lv-LV-NilsNeural", help="or lv-LV-EveritaNeural (female)")
    g.add_argument("--rate", default="+0%", help="e.g. -5%%")
    g.add_argument("--pitch", default="+0Hz")
    g = p.add_argument_group("piper")
    g.add_argument("--model", type=Path, default=ROOT / "models" / "lv_LV-aivars-medium.onnx")
    g.add_argument("--length-scale", type=float, default=1.0, help=">1 slower, <1 faster")
    g = p.add_argument_group("openai")
    g.add_argument("--openai-model", default="gpt-4o-mini-tts")
    g.add_argument("--voice", default="onyx", help="e.g. onyx, ash, echo (male); coral, nova, shimmer (female)")
    g.add_argument("--speed", type=float, default=1.0)
    g.add_argument("--instructions", default=OPENAI_INSTRUCTIONS)
    args = p.parse_args()

    engines = {"edge": edge_engine, "piper": piper_engine, "openai": openai_engine}
    synth = engines[args.engine](args)
    voice_name = {
        "edge": f"edge:{args.edge_voice}",
        "piper": args.model.stem,
        "openai": f"openai:{args.openai_model}:{args.voice}",
    }[args.engine]
    args.out.mkdir(parents=True, exist_ok=True)

    with args.map.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    manifest = []
    for row in rows:
        if args.only and row["id"] not in args.only:
            continue
        if row["status"].startswith("PROVISIONAL") and not args.include_provisional:
            print(f"skip  {row['id']:<22} (provisional wording)")
            continue
        text = row[args.text_column]
        target = args.out / f"{row['id']}.wav"
        synth(text, target)
        with wave.open(str(target), "rb") as wf:
            rate, ch, width, frames = wf.getframerate(), wf.getnchannels(), wf.getsampwidth(), wf.getnframes()
        manifest.append({
            "id": row["id"],
            "text": text,
            "file": target.name,
            "sample_rate": rate,
            "channels": ch,
            "bits": width * 8,
            "duration_s": round(frames / rate, 3),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        })
        print(f"ok    {row['id']:<22} {frames / rate:5.2f}s  {text}")

    (args.out / "manifest.json").write_text(
        json.dumps({"voice": voice_name, "files": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
