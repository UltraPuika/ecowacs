# Backup and restore procedure

No backup exists yet, because no original files could be read from the robot.
Use this procedure as soon as a supported way to read them exists.

## Back up (before any change)

1. Copy the original voice pack or files **unchanged** into
   `backup/vault/<YYYY-MM-DD>/`. Use a byte-exact copy, with no re-encoding and
   no unzip-and-rezip. `backup/vault/` is git-ignored because the files are
   Ecovacs content.
2. Create the reference inventory once, from the first copy:
   ```powershell
   .\.venv\Scripts\python.exe scripts\inspect_audio.py backup\vault\<date> --out audio\original\manifest.json
   ```
3. Make a second copy on separate media, such as a USB drive or NAS, and verify it:
   ```powershell
   .\.venv\Scripts\python.exe scripts\inspect_audio.py E:\deebot-voice-backup\<date> --verify audio\original\manifest.json
   ```
4. Record the robot's firmware version, current voice language, and the date in
   `backup/vault/<date>/NOTES.txt`.

Never modify files inside `backup/vault/`. Work on copies in
`audio/original/files/`.

## Restore

Follow [../ROLLBACK.md](../ROLLBACK.md).
