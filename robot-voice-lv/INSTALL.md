# Installation

## 1. Generate the Latvian audio (works now)

Requirements: Python 3.10+, about 70 MB of disk space for the voice model,
and internet access once to download it. Optional: `ffmpeg` and `ffprobe` on
PATH, needed only for `match_format.py` and richer `inspect_audio.py` output.

Windows PowerShell, run from `robot-voice-lv/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scripts\requirements.txt
.\.venv\Scripts\python.exe -m piper.download_voices --download-dir models lv_LV-aivars-medium
.\.venv\Scripts\python.exe scripts\generate_latvian.py --include-provisional
```

Linux / Raspberry Pi:

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python -m piper.download_voices --download-dir models lv_LV-aivars-medium
.venv/bin/python scripts/generate_latvian.py --include-provisional
```

Output: `audio/latvian/<id>.wav` plus `audio/latvian/manifest.json`, which
records the duration and SHA-256 of each file.

The default engine is **`edge`**: free Microsoft neural voices with no key
(`lv-LV-NilsNeural` male, `lv-LV-EveritaNeural` female). It needs internet and
sends only the announcement texts to Microsoft. Output is 24000 Hz, mono,
16-bit PCM with leading and trailing silence trimmed. Options:

```powershell
--edge-voice lv-LV-EveritaNeural --text-column latvian_female --out audio\latvian-female   # female set
--rate=-5%                         # slower (use "=", the value starts with "-")
--engine piper                     # fully offline, more robotic
```

### More natural voice: OpenAI `gpt-4o-mini-tts` (paid, cloud)

Only the announcement texts are sent to OpenAI. The output is 24000 Hz, mono,
16-bit PCM and overwrites the files in `audio/latvian/`.

```powershell
$env:OPENAI_API_KEY = '<your key>'
.\.venv\Scripts\python.exe scripts\generate_latvian.py --engine openai --include-provisional
# other voice / speed:  --voice ash --speed 0.95
```

## 2. Install on the robot: **BLOCKED**

There is no supported mechanism. See [RESEARCH.md §5](RESEARCH.md#5-blockers-and-what-would-unblock-them).
Do **not**:

- flash firmware
- factory-reset the robot
- open it to use UART
- use published exploits
- intercept the robot's TLS traffic

### Owner checks (safe, read-only)

1. In **Ecovacs Home**, go to **robot → Settings → Voice** and write down the
   languages offered. If **Latvian** is listed, select it. That is the official
   and complete solution, and the rest of this document is not needed.
2. Note the firmware version. This repo's app shows it under
   **Iestatījumi → Diagnostika un savienojums** when it runs in `ecovacs` mode, not `demo`.
3. Ask Ecovacs support for Latvian or custom voice-pack support. Quote model
   **DEEBOT X9 PRO OMNI**, the firmware version, and **lv-LV**.

## 3. Use the working alternative now

Latvian announcements can play on a speaker or phone, driven by the robot's real
state through this repo's backend and Home Assistant with Piper. Follow
[../docs/LATVIAN_VOICE.md](../docs/LATVIAN_VOICE.md). This alternative does not
change the robot.

## 4. If a supported install path becomes available later

Each step needs explicit owner approval before you continue.

The target is the **English (Canada)** voice pack only, used as the "Latvian
slot". Other languages and the firmware stay untouched. Keep the app set to
English (Canada) and automatic updates off. The full agent prompt is in
[INSTALL_PROMPT.md](INSTALL_PROMPT.md).

1. **Back up.** Copy the original voice pack off the robot without changing it,
   following [backup/README.md](backup/README.md). Make two copies on separate
   media, and verify both with `inspect_audio.py --verify`.
2. **Inventory.** Run:
   ```powershell
   .\.venv\Scripts\python.exe scripts\inspect_audio.py audio\original\files --out audio\original\manifest.json
   ```
   Then check the following:
   - Note the codec, sample rate, bit depth, channels, and any container or
     signature files.
   - If the pack is signed or encrypted and there is no official custom-pack
     mechanism, **stop here**.
3. **Map.** Listen to each original clip and fill `original_file` in
   `voice_map.csv`. Add rows only for clips whose meaning you have confirmed.
4. **Match the format.** Run:
   ```powershell
   .\.venv\Scripts\python.exe scripts\match_format.py --originals audio\original\files
   ```
5. **Proof of concept.** Replace **one** harmless clip, for example
   `cleaning_done`, using the supported mechanism only. Then:
   - Trigger the clip and listen to it.
   - Check that cleaning, docking, and the app still work.
   - Perform a full rollback ([ROLLBACK.md](ROLLBACK.md)) once to prove it works.
6. **Full set.** Install the full set and run the test matrix below.

### Test matrix (only on the real X9 PRO OMNI)

| Scenario | How to trigger | Pass |
|---|---|---|
| Startup | Power cycle | Clip plays and the robot connects to the app |
| Start / pause / resume | App buttons | Correct Latvian clip each time |
| Completion | Short room clean | "Tīrīšana pabeigta." plays |
| Return / charging | "Atgriezties uz staciju" | Return clip, then charging clip |
| Water tank | Remove the clean-water tank at the station | Water clip plays |
| Dustbin | Remove the dust bin | Dustbin clip plays |
| Stuck | Gently block the robot | Stuck clip plays, and the robot recovers once it is freed |
| Error | Lift the robot | Error clip plays, or the original clip if that one is unmapped |
| Regression | Full clean | Map, cleaning, and docking are unchanged; no reboots |
| Restore | [ROLLBACK.md](ROLLBACK.md) | Original voice is back |
