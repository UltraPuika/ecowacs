# Voice mapping

**Status: the original-clip column is UNKNOWN for every row.** The robot's
announcement files could not be obtained (see `RESEARCH.md`), so nothing below
has been matched to a real clip. Per the task rules, no translation is assigned
to an unidentified clip. This file lists the Latvian target phrases only, and
the English "intent" column is taken from the task description, not from the robot.

| Latvian text (target) | Intent (from task description) | Original clip / ID | Verified |
|---|---|---|---|
| Sāku tīrīšanu. | Starting cleaning | UNKNOWN | no |
| Uzsāku telpas tīrīšanu. | Starting room cleaning | UNKNOWN | no |
| Atgriežos uz uzlādes staciju. | Returning to charging station | UNKNOWN | no |
| Sāku uzlādi. | Charging started | UNKNOWN | no |
| Tīrīšana pabeigta. | Cleaning completed | UNKNOWN | no |
| Lūdzu, pārbaudiet ūdens tvertni. | Please check water tank | UNKNOWN | no |
| Lūdzu, iztukšojiet putekļu tvertni. | Please empty the dust bin | UNKNOWN | no |
| Putekļu tvertne ir pilna. | Dust bin is full | UNKNOWN | no |
| Esmu iestrēdzis. | I am stuck | UNKNOWN | no |
| Man nepieciešama palīdzība. | I need help | UNKNOWN | no |

Machine-readable copy: `audio/phrases_lv.json` (input of `scripts/generate_latvian_tts.py`).

## Language notes

* "Atgriežos **uz** uzlādes staciju" (direction, accusative) is correct for "returning
  to the station". The task text also had "uzlādes stacijā" (locative, "in the
  station"), which means "at/in the station", so I used the first.
* "Esmu iestrēdzis" uses the masculine form to agree with "robots". If the voice
  is female and you prefer the robot to speak as "she", use "iestrēdzis" →
  "iestrēdzi" consistently in all phrases. Decide once and apply everywhere.
* Messages that exist on the robot but are not in this list (for example mop
  washing, dust-bag, low battery, relocation) cannot be listed until the real clip
  list is known.

## Voice

Piper `lv_LV-aivars-medium` (a male voice) is the only Latvian Piper voice I found
listed. Whether it matches the robot's original voice gender and tone is
unknown. A natural-sounding result **has not been heard by anyone**: Piper's
Latvian model could not be downloaded in this session, so no clip was generated.
