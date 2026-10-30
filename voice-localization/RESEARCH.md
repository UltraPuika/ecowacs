# Research: voice announcements on the DEEBOT X9 PRO OMNI

Date: 2026-10-30. **Result: Phase A (research) is finished as far as public
information allows. Phase B (discovery) is blocked, so no audio was extracted,
replaced or installed.** Nothing was tested on a robot. No robot, firmware image or
network path to a robot was available.

Evidence levels used below: **READ** = I read the source myself in this session;
**SNIPPET** = a search-result summary, not read in full; **UNKNOWN** = no source found.

## 1. What is established

| # | Finding | Level | Source |
|---|---|---|---|
| 1 | The library profile for this exact model (`ilt3k8`, "DEEBOT X9 PRO OMNI") exposes **no command to read or set a voice language or voice pack**. Voice-related commands are only `playSound` (the "find the robot" sound), `setVolume` and the YIKO voice-assistant on/off switch. | READ | `deebot_client/hardware/ilt3k8.py` and a search of every command name in `deebot_client/commands` (deebot-client 18.7.0, git `1d9b498`) |
| 2 | The Home Assistant Ecovacs integration exposes none of this either: no voice, language or audio entity. | READ | `home-assistant/core` `homeassistant/components/ecovacs/` (volume number, `locate` button only) |
| 3 | Upstream **Valetudo** (the usual local-control project for rooted robots) does not support Ecovacs: its docs do not mention Ecovacs or Deebot at all. | READ | `Hypfer/Valetudo` `docs/` (grep) |
| 4 | There is a separate community research repo for the **Deebot X1 Omni** (not the X9). **The X9 PRO OMNI is not mentioned.** It says the X1 has a secondary Baidu DU1906 voice DSP with its own SPI flash, used for the wake word. | READ | [GrahamKowalski/ecovacs-x1-research](https://github.com/GrahamKowalski/ecovacs-x1-research) `README.md`, `docs/hardware.md` |
| 5 | On the **X1**, spoken prompts are selected by **numeric audio IDs** sent to an `/audio/AudioPlay` topic (for example 31 = "I am here", 24 = "go charge"). That suggests prerecorded clips chosen by ID. The same repo lists voice-pack management as an unimplemented stub, so even that project has not worked out how voice packs are stored or installed. | READ (X1 only) | same repo, `research/settings-coverage-2026-10-26.md`, `docs/capability-matrix.md` |
| 6 | I found **no official Ecovacs page** listing the robot voice languages of the X9 PRO OMNI, nor any custom-voice feature for it. A US product page mentions the YIKO assistant for English commands. | SNIPPET | web search, 2026-10-30 |
| 7 | The ECOVACS HOME app's own interface languages (it added Czech, Slovak and Dutch) are a separate thing from the robot's spoken voice. App-language support says nothing about the robot's voice. | SNIPPET | App Store listing via web search |
| 8 | Public security research by Dennis Giese et al. (DEF CON 32, HITCON 2024, 37C3) covers other Ecovacs models. A snippet of the 37C3 slides mentions "the beginning of custom software and voice packages" for **rooted** robots of other models. I could not read these slides: `dontvacuum.me` is outside this session's allowed network. | SNIPPET | web search; [DEF CON 32 slides](https://dontvacuum.me/talks/DEFCON32/DEFCON32_reveng_hacking_ecovacs_robots.pdf) (not readable here) |

## 2. What is unknown and cannot be learned without the robot

* Where X9 PRO OMNI voice audio is stored: local flash, a firmware partition, a
  downloaded package, or a separate audio chip.
* Audio format, sample rate, channels, codec, metadata and language identifiers.
* Whether voice packs are downloaded through the ECOVACS HOME app, and whether
  they are signed or encrypted.
* Whether the app lists Latvian (or any list of languages) for this robot, and
  whether any custom-voice mechanism exists for it.
* The firmware version, signing scheme and update path.

I did not guess any of these. In particular, I did **not** assume that the X1
findings (finding 4 and 5) apply to the X9.

## 3. Why work stops here

1. **There is no supported mechanism.** Neither the library, Home Assistant, nor
   any documentation I could find offers a way to select or install a voice
   pack on this model. (Option 1 in the task: official custom voice pack.)
2. **The only known route to the audio files is root access** to the robot. The
   public work on other models obtains it through physical disassembly or
   security vulnerabilities. The task rules out exploiting vulnerabilities,
   bypassing authentication, and flashing without explicit approval. I have not
   attempted any of it, and I have no physical access in any case.
3. **No firmware image is available** to inspect offline. Ecovacs does not
   publish firmware, and I did not try to obtain it by any other means.
4. The robot is in a different house from the Home Assistant system and from
   me. Nothing here can see it.

Per the task's own rule ("if the firmware requires signatures and no supported
mechanism exists, stop and report"), I am stopping and reporting. Whether the
firmware is actually signed is UNKNOWN, so this is a stop on missing access and
missing mechanism, not a proven impossibility.

## 4. What you can do next (safe, in order)

1. **Check the official app for the voice language list.** In ECOVACS HOME:
   robot → settings → look for "Voice", "Voice language" or "Voice pack". Send me
   the list of languages and any voice packs offered, plus a screenshot. If
   Latvian is there, select it. That is the best case and needs no modification.
2. **Ask Ecovacs support** whether Latvian voice (or custom voice packs) is
   planned for the X9 PRO OMNI, giving the robot's firmware version.
3. **Keep using the Home Assistant announcements** already built into the main
   app (`docs/LATVIAN_VOICE.md`). They speak Latvian on a speaker or as a phone
   notification, and need no change to the robot.
4. If you still want robot-side audio, the only path is root access to your
   own robot. That is physical, can brick a robot that costs over €1,000, can
   void the warranty, and may break cloud features. It is outside this task's
   rules, and I do not recommend it. If you decide to go there yourself, do it
   with a spare robot first, and see `backup/README.md` for the minimum safety
   requirements.

## 5. Information needed to continue to Phase B

* The firmware version and the model code shown in the app (and in the app's
  Diagnostics page under "Modelis").
* The outcome of step 1 above (language list and screenshots).
* Whether the robot downloads anything when you change the voice in the app
  (the app usually shows a download progress or size). Do not capture or
  intercept traffic; just report what the app shows.
* Written confirmation that the robot belongs to you and that you accept the
  risks, before any step that modifies it.

## 6. Sources not reachable from this session

`dontvacuum.me` (Giese's slides) and `privacysmarthome.com` (a rooting guide) were
blocked by the session's network policy, and `huggingface.co` (the Piper voice
files) as well. If you want me to read them, allow those hosts in the
environment's network settings.
