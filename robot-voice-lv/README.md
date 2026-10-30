# Latvian voice announcements for DEEBOT X9 PRO OMNI

Status: **Latvian audio has been generated, but it is not installed on the robot.**
No supported and non-invasive way to load custom audio onto the X9 PRO OMNI was
found. Nothing on the robot has been changed. See [RESEARCH.md](RESEARCH.md).

| Phase | Result |
|---|---|
| A: Research | Done. See [RESEARCH.md](RESEARCH.md) |
| B: Discovery | **Blocked.** There is no legitimate shell, file, or voice-package access to the X9 PRO OMNI. The robot was also not connected to this workspace because the backend runs in `demo` mode. |
| C: Proof of concept on the robot | **Not possible** with the current access |
| D: Latvian audio | Done offline: two voices with 12 WAV files each, in [audio/latvian/](audio/latvian/) (male) and [audio/latvian-female/](audio/latvian-female/) (female), mapped in [VOICE_MAPPING.md](VOICE_MAPPING.md) |
| E: Install and verify on the robot | **Not possible.** The working alternative is to play Latvian announcements on a speaker through Home Assistant. See [../docs/LATVIAN_VOICE.md](../docs/LATVIAN_VOICE.md) |

## Contents

| Path | Purpose |
|---|---|
| [RESEARCH.md](RESEARCH.md) | Voice architecture findings and blockers. Marks what is verified and what is not |
| [VOICE_MAPPING.md](VOICE_MAPPING.md) | Mapping from original announcements to Latvian |
| [voice_map.csv](voice_map.csv) | Machine-readable mapping, used by the scripts |
| [INSTALL.md](INSTALL.md) | How to generate the audio, why robot installation is blocked, and the gated procedure to follow if a supported path appears |
| [ROLLBACK.md](ROLLBACK.md) | Rollback steps |
| [backup/README.md](backup/README.md) | Backup and restore procedure |
| [audio/original/README.md](audio/original/README.md) | Why it is empty and how to fill it legitimately |
| `audio/latvian/` | Male voice (`lv-LV-NilsNeural`): 12 WAV files and `manifest.json` |
| `audio/latvian-female/` | Female voice (`lv-LV-EveritaNeural`): 12 WAV files and `manifest.json` |
| [INSTALL_PROMPT.md](INSTALL_PROMPT.md) | Prompt for an AI agent or engineer to carry out a safe, gated installation on the robot |
| `scripts/generate_latvian.py` | Text-to-speech (TTS) generation with Piper `lv_LV-aivars-medium`, offline |
| `scripts/inspect_audio.py` | Read-only inventory of original files and backup hash verification |
| `scripts/match_format.py` | Transcodes the Latvian files to each original's codec, sample rate, and channel layout. Runs only when the originals are known. |

## Quick start (Windows PowerShell, from this folder)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scripts\requirements.txt
# male voice -> audio\latvian
.\.venv\Scripts\python.exe scripts\generate_latvian.py --include-provisional
# female voice -> audio\latvian-female
.\.venv\Scripts\python.exe scripts\generate_latvian.py --include-provisional --edge-voice lv-LV-EveritaNeural --text-column latvian_female --out audio\latvian-female
```

On Linux or a Raspberry Pi, use `.venv/bin/python` instead.
