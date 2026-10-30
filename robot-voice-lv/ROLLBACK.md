# Rollback

## Current state

**Nothing on the robot has been modified**, so there is nothing to restore on it.
Only local files exist.

| What | How to undo |
|---|---|
| Robot voice language changed in Ecovacs Home | Go to **Ecovacs Home → robot → Settings → Voice** and select the previous language. The pack is downloaded again from Ecovacs. |
| Latvian speaker announcements (Home Assistant alternative) | In this app, go to **Iestatījumi → Paziņojumi latviski** and switch off **Ieslēgt paziņojumus latviski**, then save. Optionally uninstall the Piper add-on in HA. |
| Robot volume lowered | Restore it in Ecovacs Home or in this app's settings. |
| Local artifacts | Delete `robot-voice-lv/.venv`, `robot-voice-lv/models`, and `robot-voice-lv/audio/latvian/*.wav`. These are local files only. |

## If files are ever replaced on the robot (future, supported path only)

1. Stop any running clean and dock the robot.
2. Verify the backup is intact:
   ```powershell
   .\.venv\Scripts\python.exe scripts\inspect_audio.py backup\vault\<date> --verify audio\original\manifest.json
   ```
   It must print `N/N files verified`.
3. Copy the backed-up files back with the **same mechanism** that installed
   them, keeping the original filenames and paths.
4. Restart the robot. Trigger 2–3 announcements, such as start, return, and
   completion, and confirm the original voice plays.
5. If anything is missing, selecting the language again in Ecovacs Home makes the
   robot download the official pack again. This is the vendor-supported last
   resort and needs no firmware flashing.
