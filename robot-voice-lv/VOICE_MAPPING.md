# Voice mapping: original to Latvian

Source of truth: [voice_map.csv](voice_map.csv). This table mirrors it.

**No original robot audio file has been identified yet** (see
[RESEARCH.md](RESEARCH.md)). Rows describe announcement *meanings* only.
When the originals become available, fill the `original_file` column after
listening to each file. Do not map by filename guesswork.

| id | Event | Original (English) | Latvian | Status | File (both voice folders) |
|---|---|---|---|---|---|
| start_cleaning | Cleaning start | Starting cleaning | Sāku tīrīšanu. | meaning confirmed | start_cleaning.wav |
| start_room_cleaning | Room cleaning start | (not given) | Uzsāku telpas tīrīšanu. | meaning confirmed | start_room_cleaning.wav |
| return_to_dock | Returning to the charging station | Returning to charging station | Atgriežos uzlādes stacijā. | meaning confirmed | return_to_dock.wav |
| charging_start | Charging start | Charging started | Sāku uzlādi. | meaning confirmed | charging_start.wav |
| cleaning_done | Cleaning completion | Cleaning completed | Tīrīšana pabeigta. | meaning confirmed | cleaning_done.wav |
| check_water_tank | Water tank warning | Please check water tank | Lūdzu, pārbaudiet ūdens tvertni. | meaning confirmed | check_water_tank.wav |
| empty_dustbin | Dustbin warning | (not given) | Lūdzu, iztukšojiet putekļu tvertni. | meaning confirmed | empty_dustbin.wav |
| dustbin_full | Dustbin full | Dustbin is full | Putekļu tvertne ir pilna. | meaning confirmed | dustbin_full.wav |
| stuck | Stuck | I am stuck | Esmu iestrēdzis. (female: Esmu iestrēgusi.) | meaning confirmed | stuck.wav |
| need_help | Needs help | (not given) | Man nepieciešama palīdzība. | meaning confirmed | need_help.wav |
| pause_cleaning | Cleaning pause | unknown | Tīrīšana pauzēta. | **provisional** | pause_cleaning.wav |
| resume_cleaning | Cleaning resume | unknown | Turpinu tīrīšanu. | **provisional** | resume_cleaning.wav |

Durations and hashes are in each folder's `manifest.json`.

Not mapped yet:

- **Startup greeting:** the original wording is unknown.
- **Error-code announcements:** they need the original clips.

Translations for these will not be invented.

## Language notes

- **Grammatical gender:** two voice sets are kept. The male set
  (`audio/latvian/`, `lv-LV-NilsNeural`) uses column `latvian`, with "Esmu
  iestrēdzis." The female set (`audio/latvian-female/`, `lv-LV-EveritaNeural`)
  uses column `latvian_female`, with **"Esmu iestrēgusi."** Every other phrase
  is the same in both.
- **Direction:** "Atgriežos uzlādes stacijā" uses the locative case, as given in
  the brief. "Atgriežos uz uzlādes staciju" also appears in the brief and is
  equally natural. Choose one and keep it consistent.
- **Quality check (Piper engine only):** Piper logged `Missing phoneme from id map: ͡` (an affricate
  tie bar) for `return_to_dock` and `need_help`. The affricates are still
  pronounced, but **listen to these two files** before approving them.
- **Tuning:** Adjust speed with `--length-scale`, where values above 1 are slower.
  Re-run it per id with `--only <id>`.
- **Duration:** the durations of the original clips are unknown, so they could
  not be matched yet.
