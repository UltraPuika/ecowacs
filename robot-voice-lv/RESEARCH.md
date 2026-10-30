# Research: voice announcements on the DEEBOT X9 PRO OMNI

Evidence levels used below:

- **Verified:** checked during this work.
- **Reported:** public information that was not re-verified here. Sources were
  not reachable from this environment.
- **Unknown:** no reliable information is available.

## 1. Summary

| Question | Answer | Level |
|---|---|---|
| Are Latvian robot announcements technically possible? | Only if audio files on the robot can be replaced. No legitimate way to do that is known for the X9 PRO OMNI. | Verified (absence of a supported method) |
| How are announcements implemented? | Prerecorded clips are played by the robot's firmware when its state changes. The language is chosen in the Ecovacs Home app, and the robot then downloads that language's voice pack. | Reported / app behaviour |
| Where are the original audio files stored? | On the robot's internal storage after download. The path, container format, and codec are unknown. | Unknown |
| Can they be replaced without firmware modification? | No supported method exists. No official custom voice pack, no local file API, and no documented shell access. | Verified for the public APIs |
| Are voice packs signed or encrypted? | Unknown for the X9 PRO OMNI. | Unknown |

## 2. Communication protocols and APIs

- **Verified:** `deebot-client`, the library behind the Home Assistant
  `ecovacs` integration and used by this repo's backend, has these JSON
  command modules: volume (`volume.py`), YIKO on/off
  (`voice_assistant_state.py`), "locate" beep (`play_sound.py`), OTA state
  (`ota.py`), and others. It has **no command to read or set the announcement
  language or upload audio**. This was checked against the `dev` branch listing
  of `deebot_client/commands/json`.
- **Verified:** The cloud protocol uses MQTT/REST through `*.ecouser.net`.
  Commands are high-level, for example `clean` and `charge`. None of them
  transfers files to the robot.
- **Reported:** Bumper is a self-hosted Ecovacs cloud. It is tested only on older
  models (Deebot 900/901, OZMO 950, and others) and does not list the X9 series.
  Redirecting the robot to a fake cloud to serve a different voice pack would
  require the robot to accept a non-Ecovacs TLS endpoint. That means bypassing
  its certificate validation, which is out of scope.

## 3. Device access

| Path | Status |
|---|---|
| Official SSH, ADB, or diagnostic shell | None documented for the X9 PRO OMNI |
| Local HTTP or file API | None documented |
| UART or debug pads | Would require opening the robot. That voids the warranty and may require breaking boot security. Not done. |
| Publicly reported vulnerabilities | **Reported:** at DEF CON 32 (Aug 2024), researchers showed that several then-current Ecovacs models could be compromised, including over BLE. Using any vulnerability is **explicitly out of scope** under the task rules. Applicability to the X9 PRO OMNI was not checked. |
| This workspace | **Verified:** the backend at `localhost:8080` runs in `mode: demo`, so no real robot was reachable from this session. |

No port scan, credential guessing, or traffic interception was performed.

## 4. Voice packages

- **App behaviour:** In Ecovacs Home, go to **robot → Settings → Voice** (or
  "Voice language"). Selecting a language downloads a pack to the robot and shows
  progress. The list of offered languages is set by Ecovacs per model and region.
  No public source lists Latvian for the X9 PRO OMNI. **The owner should
  confirm this in the app.**
- **Unknown:** The pack container (archive or raw files), audio codec, sample
  rate, file naming, language identifiers, and whether a signature or hash is
  checked before the pack is installed.
- **Unknown:** Whether a custom pack would survive OTA firmware updates.
- **Not applicable:** Older-model techniques, such as replacing files on rooted
  Xiaomi/Roborock or old Deebot units, were **not assumed** to apply here.

## 5. Blockers and what would unblock them

| # | Blocker | What would be needed |
|---|---|---|
| 1 | There is no official way to load a custom or Latvian voice | Ecovacs adds Latvian, or user-uploaded packs. Ask Ecovacs support, quoting model **X9 PRO OMNI**, your firmware version, and **lv-LV**. |
| 2 | There is no legitimate file-system access | A vendor-documented developer or debug mode, or a community root method for this exact model that does **not** depend on exploiting a vulnerability. The owner must approve it explicitly. |
| 3 | The original audio cannot be obtained | It becomes available through (2), or Ecovacs provides it. Do not capture the robot's TLS traffic by defeating its certificate checks. |
| 4 | Signing is unknown | Only knowable after (2) or (3). If the pack is signed and no custom-pack mechanism exists, **stop**. Under the task rules this is a hard limit. |

## 6. What can be done now

1. **Generate Latvian audio offline.** This is done and ready to use if (1) or
   (2) is resolved later.
2. **Play announcements on a speaker or phone near the robot.** This is
   implemented in this repo's backend through Home Assistant TTS, with Piper
   `lv_LV-aivars-medium`. It reacts to the robot's real state changes from the
   cloud. See [../docs/LATVIAN_VOICE.md](../docs/LATVIAN_VOICE.md).
3. **Optionally lower the robot's own volume** in the app or in this app's
   settings, so the robot's original language does not compete with the speaker.

## 7. Risks and compatibility limits

- Any firmware-level change risks bricking the robot, voiding the warranty,
  breaking OTA updates, and leaving it without security patches.
- Rooting methods based on vulnerabilities are fragile and can be closed by an
  OTA update at any time.
- If an install path is ever found, an OTA update or a voice-language change in
  the app may overwrite the custom pack. The restore procedure in
  [ROLLBACK.md](ROLLBACK.md) must be kept available.
- Piper output is 22050 Hz mono 16-bit PCM. The robot's real format is unknown.
  `scripts/match_format.py` transcodes to it only after the originals have been
  inspected.
