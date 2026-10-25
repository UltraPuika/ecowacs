# Home Assistant setup

The app uses the official Home Assistant **Ecovacs** integration as its only
connection to the robot. See [CAPABILITY_AUDIT.md](CAPABILITY_AUDIT.md#2-integration-choice) for why.

## 1. Add the Ecovacs integration

1. In HA go to **Settings → Devices & services → Add integration → Ecovacs**.
2. Enter your Ecovacs account e-mail and password, and choose the cloud server
   (not self-hosted). The integration docs warn that some special characters in
   passwords, such as `-` and `?`, can cause problems.
3. The robot appears as a device with a `vacuum.…` entity.

## 2. Enable the entities this app benefits from

HA disables some Ecovacs entities by default. Open **Settings → Devices &
services → Ecovacs → (your robot)**, click each entity below, open ⚙ settings,
and switch **Enabled** on:

| Entity | Why |
|---|---|
| **Error** (sensor) | Error *codes*. Without it the app can only say "Nepieciešama uzmanība" with no detail. |
| **Last job** (event) | Reliable "cleaning finished" for history and the "Tīrīšana ir pabeigta" announcement. |
| Carpet auto fan speed boost (switch) | Shows the setting in the app |
| Continuous cleaning (switch) | Shows the setting in the app |

After enabling them, open the app at **Iestatījumi → Diagnostika → Pārlasīt
Home Assistant**. The diagnostics page lists any recommended entities that are
still disabled.

## 3. Create a long-lived access token

Go to **HA profile (bottom-left) → Security → Long-lived access tokens →
Create token**. Name it, for example, "Robota lietotne", copy it into `HA_TOKEN`
in `.env`, then restart with `docker compose up -d`.

The token works with the permissions of the user who created it. You can create
a dedicated non-admin HA user for the token. The app uses only these:

- WebSocket: `get_states`, `subscribe_events` (`state_changed`),
  `config/entity_registry/list`, `config/device_registry/list`, `get_services`, `call_service`
- REST: `GET /api/image_proxy/<map entity>`
- Services: `vacuum.start/pause/stop/return_to_base/locate/set_fan_speed/send_command`
  (`spot_area`, `custom_area`), `select.select_option`, `switch.turn_on/off`,
  `number.set_value`, `button.press`, `homeassistant.update_entity`,
  `tts.speak`, `media_player.volume_set`, `notify.*`

## 4. Entity discovery

The app never guesses entity IDs. It reads HA's entity registry, takes the
Ecovacs `vacuum` entity, and finds its sibling entities on the same device by
their unique-ID suffix (for example `_battery_level`, `_work_mode`, `_map`).
Renaming entities in HA is therefore safe.

If you have more than one Ecovacs robot, set `HA_VACUUM_ENTITY=vacuum.xyz` in `.env`.

## 5. Latvian announcements

See [LATVIAN_VOICE.md](LATVIAN_VOICE.md). In short:

1. Install the **Piper** add-on (or Wyoming Piper container) with voice **`lv_LV-aivars-medium`**.
2. Add the Wyoming integration so that a `tts.piper` entity exists.
3. In the app, go to **Iestatījumi → Paziņojumi latviski**. Choose `tts.piper`
   and a speaker (`media_player.…`), press **Pārbaudīt**, then **Saglabāt**.
4. Optional: choose **Ziņa tālrunī** (`notify.mobile_app_<phone>`) to get
   notifications through the HA Companion app.

## 6. Which events are announced, and how reliable are they

| Announcement | Trigger | Reliability |
|---|---|---|
| "Robots ir sācis tīrīšanu." / "Sāku tīrīšanu: Virtuve." | vacuum state goes from docked or idle to cleaning | Reliable. Room names are included only when this app started the job. |
| "Robots atgriežas uz uzlādes staciju." | state becomes `returning` | Reliable. This also fires when the robot goes to recharge mid-job. |
| "Tīrīšana ir pabeigta." | **Last job** event `finished` / `finished_with_warnings` | Reliable, but needs the entity enabled. Not announced for `manually_stopped`. |
| "Robots ir iestrēdzis. …" / "Robotam nepieciešama uzmanība. …" | new error code (Error sensor) or `error` state | Reliable when the robot reports it |
| "Neizdevās sākt tīrīšanu. …" | a start command from this app failed | Reliable |

The app never announces anything right after it reconnects to HA, and repeats
the same message at most once every 5 minutes.
