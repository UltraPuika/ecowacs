# Backup

**There is nothing to back up yet**, because no file has been read from the
robot. This page lists the minimum a future modification must meet.

Before any change to the robot:

1. Copy every file that will be replaced to storage **off the robot** (at least
   two places), keeping the original filenames and directory structure.
2. Record a SHA-256 checksum of each file (`sha256sum * > SHA256SUMS`) and keep it
   with the copies. Verify the copies against it.
3. Record the firmware version, the model code, and the date.
4. Do not continue if any backup cannot be verified.
5. Never store the only copy in this repository's working tree on the robot's
   machine or on a device that may be lost. Do not commit firmware or vendor
   audio to a public repository: it belongs to Ecovacs.

Restoring means putting the verified original files back and checking that the
checksums match what the robot now holds. Test this restore before relying on it.
