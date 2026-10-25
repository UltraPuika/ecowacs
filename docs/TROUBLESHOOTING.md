# Troubleshooting

Start with **Iestatījumi → Diagnostika un savienojums** in the app. It shows the
connection state, the HA version, the discovered entities, entities that are
disabled in HA, recent events and recent commands. **Lejupielādēt diagnostiku**
exports all of it as JSON with secrets removed, so you can share it safely.

## The app does not open on the phone

- The phone must be on the **same Wi-Fi** as the Pi. Mobile data will not work.
- Run `docker compose ps` on the Pi. Both services should show as `healthy`.
- Check that you use the right address, `http://<pi-ip>:8080`, and that the Pi's IP has not changed.

## "Nav savienojuma ar lietotnes serveri"

The phone cannot reach the Pi, or the backend is down. Run
`docker compose logs backend`, then `docker compose restart`.

## "Nav savienojuma ar Home Assistant"

- `HA_URL` must be reachable **from the container**. Use the LAN IP, not
  `localhost` or `homeassistant.local` (mDNS often does not work inside containers).
- Test it from the Pi: `curl -s -o /dev/null -w "%{http_code}" http://<ha-ip>:8123/api/` should print `401`, which means HA is reachable.
- **"Home Assistant noraidīja piekļuves pilnvaru"**: the token is wrong or was
  deleted. Create a new one, update `.env`, and run `docker compose up -d`.
  After a token is rejected, the app waits **10 minutes** between attempts, so
  it does not trigger HA's IP ban. Restart the backend to retry at once after
  you fix the token.

## "Nav savienojuma ar robotu" while HA is connected

- The robot is offline, asleep or powered off, or the Ecovacs cloud is down.
- Check whether the robot also shows as unavailable in the Ecovacs Home app.
- In HA, check **Settings → Devices & services → Ecovacs** for errors, and
  reload the integration if needed.

## "Dati var būt novecojuši"

The robot has sent nothing for `STALE_AFTER` seconds (default 15 minutes). A
docked robot can stay silent for a while, so this does not always mean a fault.
The app shows the last-update time rather than presenting old data as current.

## "Home Assistant nav atrasts neviens Ecovacs robots"

The Ecovacs integration is not set up in HA, or the robot belongs to a
different account. If you have several robots, set `HA_VACUUM_ENTITY`.

## No error details, only "Nepieciešama uzmanība"

Enable the **Error** sensor entity in HA. See [HOME_ASSISTANT.md](HOME_ASSISTANT.md#2-enable-the-entities-this-app-benefits-from).

## "Cleaning finished" is never announced, or history sessions never end

Enable the **Last job** event entity in HA. Without it, history guesses the end
of a job when the robot docks (shown as "Beigas nav zināmas"), and the
"finished" announcement is not sent.

## Command says "Komanda nosūtīta, bet robots vēl nav apstiprinājis"

HA accepted the command, but the robot's state did not change within
`VERIFY_TIMEOUT` (25 s). The robot may be slow, asleep or blocked. Look at the
robot before pressing again. Pressing the same button within 4 seconds is ignored on purpose.

## No map / "Karte nav pieejama"

- The robot may not have finished a mapping run yet.
- Press **Atjaunot karti** and wait a few seconds.
- Check that the HA **Map** image entity is enabled and shows a picture in HA.

## Rooms missing or wrong in the room list

The room list comes from the active map. After rooms are edited in the Ecovacs
app, press **Atjaunot karti**. If you switched floors, check the active map.
Room IDs change when a map is rebuilt; the app then refuses old selections with
"Izvēlētā telpa kartē vairs nav atrodama".

## Announcements are silent

1. Press **Pārbaudīt** in the announcement settings. The result shows the error from HA.
2. Check that the TTS entity works in HA → Developer tools → Actions (`tts.speak`).
3. Some speakers ignore `volume_set`. Set the volume to "Nemainīt".
4. The last announcement problems appear in Diagnostika → Pēdējie notikumi.

## Forgot the app password

Change `APP_PASSWORD` in `.env` and run `docker compose up -d`. This logs out every device.

## Collecting logs for a bug report

```bash
docker compose logs --since 1h backend > backend.log
```

Logs pass through a redaction filter, but still read them before sharing.
