# Prompt: install Latvian voice announcements on the DEEBOT X9 PRO OMNI

Copy everything below the line into an AI coding agent, or give it to an
engineer. It assumes the agent has this repository open and, if the owner
provides one, a **legitimate** way to access the robot.

---

## Role

Act as a senior embedded Linux engineer and audio localization specialist. You
are working for the **owner** of one ECOVACS DEEBOT X9 PRO OMNI. Your goal is to
make the robot's prerecorded voice announcements play in Latvian, using
audio files that have already been prepared.

## What already exists (read first)

Everything is in `robot-voice-lv/` in this repository.

- `RESEARCH.md`: findings so far. No supported way to load custom audio onto
  this model is known. The voice pack location, format, and signing are
  **unknown**.
- `voice_map.csv`: one row per announcement. It has columns `id`, `event`,
  `latvian` (male text), `latvian_female` (female text), `status`, and
  `original_file`. `original_file` is currently empty for every row.
- `audio/latvian/`: male voice (`lv-LV-NilsNeural`). Contains 12 WAV files
  (24000 Hz, mono, 16-bit PCM), plus `manifest.json` with SHA-256 hashes.
- `audio/latvian-female/`: female voice (`lv-LV-EveritaNeural`), in the same
  format and with the same file names.
- `scripts/inspect_audio.py`: read-only inventory of a folder; `--verify` checks
  a backup against an inventory.
- `scripts/match_format.py`: transcodes the Latvian files to each original
  file's codec, sample rate, and channel layout, keeping the original filename.
- `INSTALL.md` §4 (gated procedure and test matrix), `ROLLBACK.md`, and
  `backup/README.md`.

Ask the owner **which voice set to install**: male (`audio/latvian`) or female
(`audio/latvian-female`). Use only that set.

## Target: the English (Canada) voice slot only

The owner wants Latvian to play whenever the app is set to **English (Canada)**.
That language is the owner's "Latvian slot".

- Replace **only** the files of the English (Canada) voice pack. Do not touch
  any other language pack, including standard or US English.
- Do **not** change firmware logic, configuration, or language-selection code to
  force a language. The app's language setting must keep working normally.
  Selecting another language and then English (Canada) again is a valid way to
  get the official audio back.
- Before you start, confirm in Ecovacs Home that **English (Canada)** is offered
  for this robot and firmware. If it is not, **stop** and ask the owner which
  language to use as the slot. Do not substitute a language yourself.
- The owner selects English (Canada) in the app **before** the backup, so that
  the robot has actually downloaded that pack. Back up exactly that pack.
- Identify the English (Canada) pack by its language identifier on the robot,
  such as a folder name, index entry, or locale code like `en_CA` or `en-CA`.
  Record the identifier. Do not assume it; verify it.
- Ask the owner to switch off automatic firmware updates in Ecovacs Home, if
  the option exists, so that an update does not replace the pack.

## Hard rules (never break these)

1. Do **not** exploit vulnerabilities, use published exploit chains, or bypass
   authentication, secure boot, or signature checks.
2. Do **not** brute-force credentials, port-scan beyond what the owner
   explicitly allows, or intercept or redirect the robot's TLS traffic, for
   example with a fake cloud or a mitmproxy CA.
3. Do **not** flash firmware, factory-reset the robot, open its case, or use
   UART/JTAG unless the owner gives explicit written approval for that specific
   step.
4. Never delete or overwrite the only copy of any original file. Back up first,
   verify the backup, and only then change anything.
5. Do not modify anything unrelated to voice audio.
6. If the voice pack is signed or encrypted and there is no official way to
   install a custom pack, **stop and report**. Do not work around it.
7. Do not claim success without testing on the real robot.
8. Never ask for or echo passwords, tokens, or keys in chat. The owner types
   them into the terminal personally.

## Step 0: Access check (stop if this fails)

Ask the owner which **legitimate** access method they have. Valid answers
include:

- an official ECOVACS developer, debug, or service mode
- a voice-pack import feature in the Ecovacs Home app
- written guidance from ECOVACS support
- a vendor-documented shell

If none exists, **stop**. Report that installation is blocked and point to
`RESEARCH.md §5`. Suggest the owner ask ECOVACS support for Latvian or custom
voice-pack support. Meanwhile, the working alternative is Home Assistant
speaker announcements, described in `docs/LATVIAN_VOICE.md`.

Record the robot's firmware version, the current voice language, and the
access method.

## Step 1: Back up (read-only on the robot)

Using only the approved access method:

1. Locate the active **English (Canada)** voice pack. Copy it **byte-exact** to
   `robot-voice-lv/backup/vault/<YYYY-MM-DD>/`.
2. Run:
   ```
   python scripts/inspect_audio.py backup/vault/<date> --out audio/original/manifest.json
   ```
3. Make a second copy on separate media and run `--verify` against it. It must
   print `N/N files verified`.
4. Write `backup/vault/<date>/NOTES.txt` containing the firmware version, the
   language (English (Canada)) and its identifier on the robot, the source path
   on the robot, and the date.

## Step 2: Analyse the original pack (no changes to the robot)

1. Copy the pack to `audio/original/files/` and work only on that copy.
2. Identify the following:
   - the container type: plain files, archive, or custom blob
   - any index, manifest, or config file that maps events to files
   - the language identifier
   - any signature, hash, or checksum files
   - the codec, sample rate, bit depth, and channel count
3. If you find a signature or encryption that you cannot satisfy legitimately,
   **stop and report** (rule 6).
4. Listen to every original clip. For each clip whose meaning you can confirm,
   set `original_file` in `voice_map.csv`.
   - Do **not** guess from file names alone.
   - Do **not** invent translations for clips you cannot identify. List them as
     "unmapped" and leave them in the original language.
5. Report the full mapping to the owner and get approval before continuing.

## Step 3: Build the Latvian pack

1. Run:
   ```
   python scripts/match_format.py --latvian audio/<chosen-set> --originals audio/original/files --out audio/latvian-pack
   ```
2. Start `audio/latvian-pack/` as a copy of the **entire** original pack. Replace
   only the mapped files with the matched Latvian files, keeping identical
   names, paths, and formats. Leave index or config files unchanged unless their
   format requires a change, such as a size or hash field. If such a change is
   needed and is not allowed by an official mechanism, stop and report.
3. Inventory the result with `inspect_audio.py` and diff it against the original
   inventory. Only the intended files may differ.

## Step 4: Proof of concept (one file only)

1. With owner approval, replace **one** harmless clip, for example
   `cleaning_done`, using the approved access method.
2. Trigger it and confirm that it plays correctly in Latvian.
3. Check that the app connects and that a short clean and docking still work.
4. **Do a full rollback** (`ROLLBACK.md`) and confirm the original voice is
   back. Also confirm that switching the app to another language and back to
   English (Canada) behaves as expected, and record whether that re-downloads
   the official pack and overwrites the Latvian files. Do not continue unless
   the rollback works.

## Step 5: Full install and verification

1. With owner approval, install the full Latvian pack the same way.
2. Run the test matrix in `INSTALL.md §4` on the real robot:
   - startup
   - start, pause, and resume
   - completion
   - return and charging
   - water tank
   - dustbin
   - stuck
   - errors
   - a full regression clean
   - a final restore test
3. Check that pronunciation is correct, that no clip is missing or silent, that
   the robot does not reboot or crash, and that cleaning, mapping, and docking
   are unchanged.

## Step 6: Report

Deliver:

1. **Feasibility:** whether installation succeeded, and if not, the exact blocker.
2. **Voice pack:** where the voice pack lives, its format, and its signing status.
3. **Changes:** every file changed on the robot, with original and new SHA-256.
4. **Mapping:** the final `voice_map.csv`, with unmapped clips listed.
5. **Test results:** pass or fail for each scenario.
6. **Rollback:** exact rollback commands, confirmed working.
7. **Risks:** an OTA update or a language change in the app may overwrite the
   pack; reinstallation steps. Remind the owner to keep the app set to
   **English (Canada)** and to keep automatic updates off.

Update `robot-voice-lv/RESEARCH.md`, `INSTALL.md`, and `ROLLBACK.md` with
the verified facts. Mark anything that was not verified.
