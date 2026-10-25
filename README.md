# Latvian DEEBOT Control

A simple Latvian-language control app for the **ECOVACS DEEBOT X9 PRO OMNI**. It
is built for people who find the official Ecovacs Home app too complicated. It
runs on your own Raspberry Pi with Docker and works in Android and desktop
browsers. You can install it on an Android phone like an app (PWA).

```
 Phone / PC browser ──LAN──► Raspberry Pi: frontend (nginx) ──► backend (FastAPI)
                                                                   │  WebSocket + REST, long-lived token
                                                                   ▼
                                               Home Assistant ── official "Ecovacs" integration
                                                                   │  (deebot-client 18.7.0, has an X9 PRO OMNI profile)
                                                                   ▼
                                                        Ecovacs cloud ◄──► robot
```

## What works

**Tested in this repository**, using automated tests with a mocked Home
Assistant and robot:

| Area | Status |
|---|---|
| Status, battery, activity, last update, connection state, stale-data warning | ✅ |
| Start, pause, resume, stop (with confirmation), return to station, "where is the robot" sound | ✅ |
| Clean selected rooms (multi-select, 1 or 2 passes) | ✅ |
| Cleaning mode (vacuum / vacuum+mop / mop after vacuum), suction power, water amount, clean count | ✅ |
| Carpet fan-speed boost, continuous cleaning, child lock, robot volume, empty dust bin | ✅ |
| Map image with robot position, trace, virtual walls and no-mop zones; "Atjaunot karti" | ✅ |
| **Hide carpets in this app's map display only** (never changes the robot) | ✅ when the map contains a carpet pixel layer (see [map limitations](docs/MAP_AND_CARPET_LIMITATIONS.md)) |
| Switch active map / floor (with confirmation) | ✅ |
| Robot error codes in plain Latvian with a next step | ✅ (needs the HA "Error" sensor enabled) |
| Local cleaning history, event log, command log, clear history (with confirmation) | ✅ |
| Diagnostics page and export with secrets removed | ✅ |
| Latvian spoken announcements via Home Assistant TTS (for example Piper `lv_LV-aivars`), phone notifications, no repeats | ✅ |
| Password login, rate-limited, signed cookies, CSRF header, no public exposure | ✅ |
| Demo mode with a permanent purple "DEMO" banner | ✅ |

**Not possible through any supported API.** The app shows no fake control for
these. Details are in [docs/CAPABILITY_AUDIT.md](docs/CAPABILITY_AUDIT.md):

- editing room borders, virtual walls or no-go zones
- deleting the map or starting a new mapping run (do this in the Ecovacs Home app)
- carpet detection sensitivity, carpet avoidance, removing detected carpets
- robot voice language and custom audio on the robot ([why](docs/LATVIAN_VOICE.md))
- overriding the robot's navigation

**Not yet verified on a real X9 PRO OMNI.** No physical robot was available
while this was built. The support statements come from the library and Home
Assistant source code. [The audit, section 5](docs/CAPABILITY_AUDIT.md#5-real-device-verification-still-required)
lists the checks to do on your robot.

## How to connect your real DEEBOT X9 PRO OMNI (summary)

1. **Home Assistant:** go to Settings → Devices & services → Add integration →
   **Ecovacs** and log in with your Ecovacs account. The robot appears as `vacuum.<name>`.
2. In HA, open the robot's device page and **enable** these disabled entities:
   **Error** (sensor), **Last job** (event), and optionally **Carpet auto fan
   speed boost** and **Continuous cleaning**. See [docs/HOME_ASSISTANT.md](docs/HOME_ASSISTANT.md).
3. In HA, create a **long-lived access token**: your profile → Security.
4. On the Pi, clone this repository, then run `cp .env.example .env`. Set
   `HA_URL`, `HA_TOKEN` and `APP_PASSWORD`.
5. Run `docker compose up -d --build`.
6. On the phone, either open `http://<pi-ip>:8080` and use **⋮ → Add to Home screen**,
   or install the **Android APK** from the GitHub Releases page ([docs/ANDROID_APP.md](docs/ANDROID_APP.md)).

Full steps: [docs/INSTALL_RASPBERRY_PI.md](docs/INSTALL_RASPBERRY_PI.md).

To try the app without a robot, set `MODE=demo` in `.env`. Everything shown is
simulated and labelled "DEMO".

## Costs and cloud dependency

Running the app costs **€0**. It uses no paid API, subscription or analytics.

The robot is controlled through the **Ecovacs cloud**, the same way the official
app and the HA integration work. If Ecovacs' servers or your internet connection
are down, the app shows "Nav savienojuma ar robotu" and does not invent a state.
HA supports a self-hosted Bumper server as an alternative, but whether it works
with the X9 is unverified.

Latvian speech via Piper runs locally on the Pi.

## Development

```bash
# backend (Python 3.12+)
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest            # 93 tests, no robot or HA needed
ruff check .
MODE=demo AUTH_DISABLED=true DATA_DIR=./data uvicorn --factory app.main:build --port 8000

# frontend (Node 22.22+ / 24)
cd frontend && npm ci
npm test                    # vitest
npm run build               # type-check + production build
BACKEND_URL=http://localhost:8000 npm run dev
```

Real-device tests are read-only and skipped by default:

```bash
REAL_HA_URL=http://192.168.1.10:8123 REAL_HA_TOKEN=... python -m pytest -m realdevice -s
```

## Documentation

- [Capability audit](docs/CAPABILITY_AUDIT.md): what the X9 PRO OMNI supports, with sources
- [Install on Raspberry Pi](docs/INSTALL_RASPBERRY_PI.md): install, update, Android PWA
- [Android app (APK)](docs/ANDROID_APP.md): download, install, signing
- [Home Assistant setup](docs/HOME_ASSISTANT.md)
- [Map and carpet limitations](docs/MAP_AND_CARPET_LIMITATIONS.md)
- [Latvian voice](docs/LATVIAN_VOICE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## Project layout

```
backend/app/
  adapters/homeassistant.py  entity discovery (registry, no guessed IDs) + snapshot + HA service calls
  adapters/ha_client.py      HA WebSocket client, reconnect with backoff, slow retry after bad token
  adapters/demo.py           simulated robot (always flagged demo=True)
  commands.py                validation, duplicate prevention, timeouts, state-verified results
  services.py                staleness, history tracker, event log, Latvian announcer
  map_svg.py                 display-only carpet hiding in the map SVG
  errors_lv.py               robot error codes → Latvian text + next step
  auth.py, redact.py         login/session, secret redaction
frontend/src/                React + TypeScript PWA (Latvian UI)
```
