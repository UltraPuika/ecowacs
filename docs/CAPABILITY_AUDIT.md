# Capability audit: ECOVACS DEEBOT X9 PRO OMNI

Audit date: 2026-10-25. Every claim below comes from source code that was read
or from documentation that was checked. Nothing in this file was tested on a
physical robot: no X9 PRO OMNI was available while this was written. The
statuses mean:

| Status | Meaning |
|---|---|
| **CONFIRMED** | The X9 PRO OMNI profile in `deebot-client` explicitly declares the capability, and the Home Assistant (HA) integration exposes it. The code path exists for this exact model, but it has **not been tested on a real device by this project**. |
| **PARTIALLY SUPPORTED** | Part of the feature is available, or it is available only indirectly or with caveats. |
| **UNVERIFIED** | The data may exist, but no source confirms its form or presence for this model. |
| **NOT SUPPORTED** | No supported API exists for this model. The app has no control for it. |

## 1. Sources examined

| Source | Version / revision | What was checked |
|---|---|---|
| [DeebotUniverse/client.py](https://github.com/DeebotUniverse/client.py) (`deebot-client`) | PyPI 18.7.0, git `1d9b498` (2026-10-21) | Model profile `deebot_client/hardware/ilt3k8.py` (docstring: *"DEEBOT X9 PRO OMNI Capabilities"*), commands, events, map renderer (`src/map/*.rs`), error table (`const.py`) |
| [Home Assistant `ecovacs` integration](https://www.home-assistant.io/integrations/ecovacs/) | `home-assistant/core` dev branch, manifest pins `deebot-client==18.7.0` | `vacuum.py`, `image.py`, `select.py`, `sensor.py`, `switch.py`, `number.py`, `event.py`, `button.py`, `strings.json`, and the docs page source in `home-assistant.io` |
| [ju1ced/ecovacs-map-data](https://github.com/ju1ced/ecovacs-map-data) | `main` | An optional HACS companion that republishes room polygons, positions and the trace as a sensor. It sends no commands. |
| [PiotrMachowski/lovelace-xiaomi-vacuum-map-card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card) | – | UI reference only. It is a Lovelace card that needs manual calibration points. It is not an Ecovacs data source and this app does not use it. |
| [rhasspy/piper VOICES.md](https://github.com/rhasspy/piper/blob/master/VOICES.md) and [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) | `master` / `main` | A Latvian voice exists: `lv_LV-aivars-medium` |

Model identification: Ecovacs devices report a `class` code, and `deebot-client`
selects the profile from that code. The X9 PRO OMNI profile is `ilt3k8`. If your
robot reports a different class (some regional variants do), the library falls
back to a generic or "unsupported" profile. The **Diagnostics** page in this app
shows what Home Assistant reports, so you can check this.

## 2. Integration choice

Two methods were evaluated:

* **A. Direct `deebot-client` in our backend.** This gives full access, but the
  backend would hold the Ecovacs password, open a second cloud MQTT session next
  to HA's, and need its own token and re-login handling. `deebot-client` 18.x
  also requires **Python ≥ 3.14**.
* **B. Home Assistant's `ecovacs` integration.** This runs the **same library at
  the same version (18.7.0)**. The HA core team maintains and updates it, it
  already handles login, token refresh and reconnects, and the user already runs
  HA on the Pi.

**Decision: B.** The control code is identical, there is one cloud session
instead of two, and our app never stores Ecovacs credentials. It needs only an
HA long-lived access token. HA is needed for TTS announcements anyway. Using
both methods would duplicate work without adding capability.

**Update:** on request, a third mode (`MODE=direct`) was added that runs method A without Home Assistant.
It uses the same library and has the same robot support; see [DIRECT_MODE.md](DIRECT_MODE.md). The
Home Assistant mode remains the default.

Cost of choosing B: anything the library supports but HA does **not** expose is
unavailable to us. That covers cleaning-log images, raw virtual-wall coordinates
and room polygons, unless the optional `ecovacs-map-data` companion is installed.
These gaps are marked in the table.

## 3. Capability table

| Feature | Status (X9 PRO OMNI) | Library / HA entity or command | Evidence | Known limitations | Implementation plan |
|---|---|---|---|---|---|
| Connection / availability | CONFIRMED | `AvailabilityEvent` via `GetBattery(is_available_check=True)` → HA entity state `unavailable` | `ilt3k8.py` `availability=` | Depends on the Ecovacs cloud. A robot that is powered off shows as unavailable. | Shows two separate states, "Nav savienojuma ar Home Assistant" and "Nav savienojuma ar robotu", plus the time of the last update. |
| Battery level | CONFIRMED | `BatteryEvent` → `sensor.<robot>_battery` (device_class battery) | `ilt3k8.py` `battery=`; HA `sensor.py` `ATTR_BATTERY_LEVEL` | – | Large % indicator on the home screen. |
| Activity (cleaning, docked, paused, returning, idle, error) | CONFIRMED | `StateEvent` (`GetChargeState`, `GetWorkState`) → `vacuum` entity state | `ilt3k8.py` `state=`; HA `vacuum.py` `_STATE_TO_VACUUM_STATE` | No "charging vs fully charged" distinction. "Docked" is shown as "Robots ir stacijā / uzlādējas". | Latvian status text and colour. |
| Start whole-home clean | CONFIRMED | `CleanV2(START)` → `vacuum.start` | `ilt3k8.py` `action=CapabilityCleanAction(command=CleanV2, …)` | – | "Sākt tīrīšanu". Success is reported only after the state changes to `cleaning`. |
| Pause / resume | CONFIRMED | `CleanV2(PAUSE)` → `vacuum.pause`; `vacuum.start` while paused sends RESUME (library `Clean._execute`) | `clean.py` lines 29-49 | – | "Pauzēt" / "Turpināt" |
| Stop | CONFIRMED | `CleanV2(STOP)` → `vacuum.stop` | HA `vacuum.py` `async_stop` | – | "Apturēt" with a confirmation dialog |
| Return to station | CONFIRMED | `Charge` → `vacuum.return_to_base` | `ilt3k8.py` `charge=` | – | "Atgriezties uz staciju" |
| Locate (play sound) | CONFIRMED | `PlaySound` → `vacuum.locate` | `ilt3k8.py` `play_sound=` | Plays the robot's built-in sound, not custom audio. | "Kur ir robots?" button |
| Room list (IDs, names) | CONFIRMED | `RoomsEvent` via `GetCachedMapInfo` / `getMapSet_V2` → `vacuum` attribute `rooms` (`{name: id}` or `{name: [ids]}` for duplicate names) | `ilt3k8.py` `rooms=`; HA `vacuum.py` `extra_state_attributes` | Names are whatever the Ecovacs app set. Unnamed rooms get the library's English default names. | Room picker with large buttons |
| Clean selected rooms | CONFIRMED | `CleanArea(SPOT_AREA, "id1,id2", cleanings)` → `vacuum.send_command` `spot_area` `{rooms, cleanings}` | `ilt3k8.py` `area=CleanArea`; HA `vacuum.py` `async_send_command` | IDs belong to the *active* map. They change if the map is rebuilt. | Multi-select rooms, then "Tīrīt izvēlētās telpas" |
| Zone (rectangle) cleaning | PARTIALLY SUPPORTED | `CleanArea(CUSTOM_AREA, "x1,y1,x2,y2", cleanings)` → `send_command` `custom_area` | same | Needs robot-coordinate rectangles. HA exposes the map only as an SVG image with no stable coordinate calibration, so drawing a zone on the image cannot be translated reliably. | Advanced section only: enter coordinates manually with a clear warning. No drag-to-draw zone tool, because it could clean the wrong spot. |
| Cleaning mode (vacuum / vacuum+mop / mop after vacuum) | CONFIRMED | `WorkMode` → `select.<robot>_work_mode` options `vacuum`, `vacuum_and_mop`, `mop_after_vacuum` | `ilt3k8.py` `work_mode types=(MOP_AFTER_VACUUM, VACUUM, VACUUM_AND_MOP)` | No "mop only" mode on this model. | Three large mode buttons |
| Suction power | CONFIRMED | `FanSpeed` → `vacuum.set_fan_speed` `quiet` / `normal` / `max` / `max_plus` | `ilt3k8.py` `fan_speed=` | – | Select in "Tīrīšanas iestatījumi" |
| Water amount | CONFIRMED | `SetWaterInfo(custom_amount)` 0–50 → `number.<robot>_water_amount` | `ilt3k8.py` `water.amount min=0 max=50` | Numeric scale only. Ecovacs does not document the meaning of each value. | Slider in settings |
| Clean count (1–2 passes) | CONFIRMED | `CleanCount` → `number.<robot>_clean_count` | `ilt3k8.py` `count=` | – | Option in settings |
| Error reporting (code + text) | CONFIRMED | `ErrorEvent(code, description)` → `sensor.<robot>_error` (state = code, attribute `description`) | `ilt3k8.py` `error=`; HA `sensor.py` `EcovacsErrorSensor` | **This HA sensor is disabled by default.** You must enable it. Without it, only the generic `error` activity is known. Code texts come from the library's table, which is not exhaustive. | Codes mapped to Latvian explanations plus a next step. Unknown codes are shown as "Kļūda Nr. X". |
| Last job result | CONFIRMED | `ReportStatsEvent` → `event.<robot>_last_job` with `finished`, `finished_with_warnings`, `manually_stopped` | HA `event.py` | Disabled-by-default diagnostic entity. Enable it for the "Tīrīšana pabeigta" announcement. | Used for history and announcements |
| Last clean area / duration | CONFIRMED | `sensor.<robot>_stats_area` (m²), `sensor.<robot>_stats_time` | HA `sensor.py` | Value of the current or last cycle. | Recorded in our history when a cycle ends |
| Cleaning history list from the robot (with per-job maps) | PARTIALLY SUPPORTED | `CleanLogEvent` (`GetCleanLogs`) exists in the library but **HA does not expose it** | `ilt3k8.py` `log=`; no HA entity | Cleaning-log map images cannot be retrieved through HA. | Our own local history (SQLite), built from observed state transitions plus robot-reported area and time. It is labelled as recorded by this app. |
| Map image | CONFIRMED | `image.<robot>_map` (SVG made by `deebot-client`), refreshed by `homeassistant.update_entity` | HA `image.py` (content type `image/svg+xml`) | A rendered image, not an editable map. For MapInfo_V2 models the library draws room shapes from vector data. | Map page shows the SVG, the time of its last update and a "Atjaunot karti" button |
| Robot and charger position, cleaning trace | CONFIRMED (inside the map image) | `PositionsEvent`, `MapTraceEvent` are rendered into the SVG | `ilt3k8.py` `position=`, `trace=`; `src/map/mod.rs` `get_svg_positions` | Position is drawn on the image. It is not available as numbers without `ecovacs.raw_get_positions` (a response-only service) or the optional `ecovacs-map-data` sensor. | Shown through the map image. Numeric positions are not used. |
| Virtual walls / no-mop zones (display) | PARTIALLY SUPPORTED | `getMapSet_V2` types `vw` and `mw` are rendered in the SVG (red / orange) | `map/__init__.py` `GetMapSetV2`; `style.rs` | Display only, and only if the robot returns them. There is no separate list. | Legend on the map page |
| Virtual walls / no-go zones (edit) | NOT SUPPORTED | No set command in the X9 profile | `ilt3k8.py` (no such capability) | – | Not offered. Use the Ecovacs Home app. |
| Room boundaries edit / merge / split / rename | NOT SUPPORTED | No command in the X9 profile | `ilt3k8.py` | – | Not offered. Use the Ecovacs Home app. |
| Active map / multiple floors | CONFIRMED | `select.<robot>_active_map` (`SetMajorMap`) | HA `select.py` `EcovacsActiveMapSelectEntity`; `ilt3k8.py` `major=CapabilitySet(...SetMajorMap)` | Switching to the wrong floor map makes the robot clean with wrong boundaries. | Shows the active map name. Switching requires confirmation. |
| Map refresh (re-download from the robot) | CONFIRMED | `homeassistant.update_entity` on `image.*_map` → `Map.refresh()` | HA `image.py` `async_update` | Re-downloads the map. It does **not** make the robot re-scan. | "Atjaunot karti" |
| Delete map / new mapping run | NOT SUPPORTED | `clear_map` exists in the library for other models, but is **not in the X9 profile** | `ilt3k8.py` | – | Not offered. The recovery guide explains how to do it in the Ecovacs app, with warnings. |
| Manual relocation | NOT SUPPORTED | `relocation` capability absent from the X9 profile (the HA "Relocate" button will not appear) | `ilt3k8.py` | – | Not offered |
| Carpet regions in the map image | UNVERIFIED | Renderer palette index 3 = "Carpet" in the **pixel** map. For MapInfo_V2 data, layer types 3/4 are "unknown" and not rendered. | `src/map/background_image.rs`, `src/map/map_info.rs` | When the X9 sends MapInfo_V2 vector data, the library renders vectors **instead of** the pixel image, so carpets may not appear at all. If carpet pixels do appear, they are a display layer in the image. | "Rādīt / slēpt paklājus kartē": recolours carpet pixels to floor colour **in our display only**. The app reports whether carpet pixels were found. |
| Carpet auto fan-speed boost | CONFIRMED | `getCarpertPressure` / `setCarpertPressure` → `switch.<robot>_carpet_auto_fan_boost` | `ilt3k8.py` `carpet_auto_fan_boost=` | Changes suction on carpets only. Does not change detection or avoidance. | Switch in settings: "Palielināt jaudu uz paklājiem" |
| Carpet detection sensitivity / carpet avoidance / mop-lifting strategy | NOT SUPPORTED | No command in the library for any model | Library-wide search for "carpet" finds only `CarpetAutoFanBoost` | Only the Ecovacs Home app can change these. | Documented workaround: use the Ecovacs app, and the no-mop zones there. |
| Edit or remove detected carpet regions on the robot | NOT SUPPORTED | – | – | – | Not offered |
| Continuous cleaning (resume after recharge) | CONFIRMED | `switch.<robot>_continuous_cleaning` | `ilt3k8.py` `continuous=` | – | Settings switch |
| Child lock | CONFIRMED | `switch.<robot>_child_lock` | `ilt3k8.py` `child_lock=` | – | Settings switch |
| Volume of robot voice | CONFIRMED | `number.<robot>_volume` (`SetVolume`) | `ilt3k8.py` `volume=` | – | Slider in settings |
| Voice assistant "YIKO" on/off | CONFIRMED in library, not exposed by HA | `VoiceAssistantStateEvent` | `ilt3k8.py` `voice_assistant=`; no HA switch | – | Not offered |
| Robot voice language selection | NOT SUPPORTED (via API) | No command in the library | Library search for voice / language finds only `VoiceAssistantState` and `Volume` | Whether Ecovacs offers Latvian as a robot voice language in its own app is **UNVERIFIED**. No source lists one. | See `LATVIAN_VOICE.md`. Use HA announcements. |
| Custom audio / voice packs on the robot | NOT SUPPORTED | – | No documented or library mechanism. Community methods need firmware or root access, which this project rejects. | – | Not offered |
| Station: empty dust bin | CONFIRMED | `button.<robot>_station_action_empty_dustbin` | `ilt3k8.py` `station.action types=(EMPTY_DUSTBIN,)` | – | Button in settings |
| Station state (washing / drying / emptying) | CONFIRMED | `sensor.<robot>_station_state` | `ilt3k8.py` `station.state=` | – | Shown as a secondary status line |
| Auto-empty frequency | CONFIRMED | `select.<robot>_auto_empty` (`auto`, `smart`) | `ilt3k8.py` | – | Not on the main UI (advanced) |
| Consumables lifespan | CONFIRMED | `sensor.<robot>_lifespan_*` | `ilt3k8.py` `life_span=` | – | Read-only list in diagnostics |
| "Areas not cleaned" detection | PARTIALLY SUPPORTED | The cleaning trace is drawn in the map SVG. No coverage data is available. | `src/map/points.rs` | We cannot compute uncleaned areas reliably. A person can only compare the trace with the room shapes visually. | The map page explains how to read the trace. No automatic "missed areas" claim. |
| Self-hosted (no cloud) operation | PARTIALLY SUPPORTED | HA supports a self-hosted [Bumper](https://bumper.readthedocs.io) server | HA docs "Self-hosted configuration" | Whether Bumper supports the X9 is **UNVERIFIED**. Setting it up redirects the robot's DNS. | Documented as an option only. The default needs the Ecovacs cloud. |

## 4. What this means for the two main problems

**Robot skips areas (problem A).** No API can change the robot's navigation. The
app can do these things:

1. show the current map, active floor and room list with IDs;
2. re-download the map;
3. start room or whole-home cleaning;
4. show the live trace in the map image;
5. walk you through a manual recovery checklist.

Deleting the map or re-mapping must be done in the Ecovacs Home app. The
checklist explains the steps and their consequences.

**Carpet regions (problem B).** Three capabilities, kept separate:

1. **Hiding carpet shapes in our interface.** Implemented. It works only if
   carpet pixels are present in the map image (UNVERIFIED for the X9). It does
   nothing to the robot.
2. **Carpet settings on the robot.** Only "carpet auto fan boost" (CONFIRMED).
3. **Changing carpet detection or avoidance behaviour.** NOT SUPPORTED through
   any API. Only the Ecovacs Home app can do this.

## 5. Real-device verification still required

These steps need to be done by you on the actual robot:

* Check that HA shows the robot with the `ilt3k8` model (Diagnostics page).
* Run `spot_area` with one room. Confirm the right room is cleaned.
* Check whether carpet pixels appear in the map. The Map page shows "Paklāji kartē atrasti: jā/nē".
* Enable the HA `Error` sensor and the `Last job` event entity, then check that errors and finished events arrive.
* Test the Piper Latvian voice on your speaker.
