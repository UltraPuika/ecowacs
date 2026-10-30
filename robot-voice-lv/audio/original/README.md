# Original audio

This folder is empty on purpose. The X9 PRO OMNI's original announcement files
could not be obtained without bypassing device security. See
[../../RESEARCH.md](../../RESEARCH.md).

If a supported method becomes available:

- Put working copies in `files/`. This folder is git-ignored because the audio is
  Ecovacs content and should not be redistributed.
- Generate `manifest.json` here with `scripts/inspect_audio.py`. It records the
  original filenames, sizes, SHA-256 hashes, detected container, sample rate,
  bit depth, channels, codec, and tags.
