# Installation

**There is no installation procedure, because no method of changing the robot's
voice has been identified.** I did not write install commands for a mechanism that
I could not verify, since a wrong command on a real robot could damage it.

## Current state

* The robot has not been touched by this project: nothing was read from it,
  written to it, flashed, or reset.
* Nothing was installed anywhere except the files in this repository.

## What you can use now

1. **The robot's own voice settings:** in ECOVACS HOME, check the voice-language
   list (see `RESEARCH.md` §4, step 1) and pick Latvian if it exists.
2. **Latvian announcements through Home Assistant:** set up as described in
   [../docs/LATVIAN_VOICE.md](../docs/LATVIAN_VOICE.md). No change to the robot.

## What a future install procedure must satisfy

It can be written only after Phase B succeeds. It must at least:

1. Use an **official or documented** mechanism, or a reversible change to a
   voice resource that is stored separately from the firmware. Firmware flashing
   only as a last resort, with your explicit written approval.
2. Start with a full backup of every file it will replace, stored off the robot,
   with checksums (`backup/README.md`).
3. Replace **one harmless clip first** (for example "I am here") and verify it
   plays, before touching anything else.
4. Use generated clips whose format is checked against the original with
   `scripts/check_audio_format.py --compare` (exit status 0).
5. Never disable signature checks, secure boot or other protections, and never
   factory-reset the robot.
6. Include a tested rollback (`ROLLBACK.md`).
7. Be tested on the real X9 PRO OMNI for each scenario in the task's testing list
   (startup, start, pause, resume, finish, return to dock, charging, water tank,
   dust bin, stuck, errors) and show no effect on cleaning.
