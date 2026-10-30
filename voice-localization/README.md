# Latvian voice on the robot itself: investigation

**Status: blocked at Phase B. Latvian announcements on the robot itself are
NOT done.** No robot audio was extracted, replaced, installed or tested. Read
[RESEARCH.md](RESEARCH.md) for the findings and the exact blocker.

| Phase | Status |
|---|---|
| A. Research | Done as far as public information allows ([RESEARCH.md](RESEARCH.md)) |
| B. Discovery (find the audio package) | **Blocked**: no supported mechanism, no firmware, no robot access |
| C. Proof of concept | Not started |
| D. Full localization | Prepared only: phrase list and generation scripts, **no clips generated** |
| E. Install and verify | Not started. No install method exists ([INSTALL.md](INSTALL.md)) |

## What works today

Latvian speech already works **outside the robot** through the main app's Home
Assistant announcements, on a speaker or as a phone notification. It has been
tested only with a mocked Home Assistant. See [../docs/LATVIAN_VOICE.md](../docs/LATVIAN_VOICE.md).

## What is in this directory

| Path | Contents |
|---|---|
| `RESEARCH.md` | Findings, evidence levels, unknowns, blockers, next steps |
| `VOICE_MAPPING.md` | Latvian target phrases (original clips: UNKNOWN) |
| `INSTALL.md`, `ROLLBACK.md`, `backup/README.md` | Why there is no install procedure, and the safety gates one would need |
| `audio/phrases_lv.json` | The Latvian phrases as input data |
| `audio/original/`, `audio/latvian/` | Empty on purpose: nothing could be extracted or generated |
| `scripts/generate_latvian_tts.py` | Piper TTS then ffmpeg conversion to a target format you supply |
| `scripts/check_audio_format.py` | Describes audio files; compares a generated clip to an original |

## The scripts

Both scripts were tested with a **stub** in place of Piper (it writes a tone), so
the conversion, overwrite protection, input validation and format comparison are
checked, but **the speech itself is not**.

```bash
sudo apt install ffmpeg
python3 -m venv .venv && . .venv/bin/activate && pip install piper-tts
# Download lv_LV-aivars-medium.onnx and .onnx.json from the Piper voices page into ./voices

# Once you have an ORIGINAL clip, read its exact format:
python3 scripts/check_audio_format.py audio/original/<clip>
# Then generate Latvian clips in exactly that format (no defaults; you must pass it):
python3 scripts/generate_latvian_tts.py --model voices/lv_LV-aivars-medium.onnx \
    --rate <Hz> --channels <1|2> --sample-format <s16|s32|flt|u8> --ext <wav>
# Verify each result against its original before using it:
python3 scripts/check_audio_format.py --compare audio/original/<clip> audio/latvian/<id>.<ext>
```

The generator refuses to overwrite an existing file. Even a clip that passes
the format check still has to be listened to by a Latvian speaker before use.

## What I need from you to go further

See section 5 of [RESEARCH.md](RESEARCH.md). The first step is quick and risk-free:
look in the ECOVACS HOME app for a voice-language list for this robot and send it to me.
