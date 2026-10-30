# Direct mode: no Home Assistant

`MODE=direct` connects the app straight to the Ecovacs cloud. It uses the **same
library as Home Assistant's Ecovacs integration** (`deebot-client` 18.7.0, which
has a profile for the X9 PRO OMNI), so the robot support is the same as in the
[capability audit](CAPABILITY_AUDIT.md). Only the way it connects is different.

**Not tested on a real robot.** The code is tested against the real library with
the network replaced, and the app was started in this mode without a login. It has
never talked to the real Ecovacs cloud, so expect to report problems from your
first login.

## What you need to know first

* **There is no local/IP connection.** The robot is reached through the Ecovacs
  cloud, even when you are on its Wi-Fi. Being on the robot's network changes
  nothing; the Raspberry Pi (or any machine running this app) only needs
  internet access.
* **The robot may be in another house.** That works: nothing is installed there.
* The app needs the **Ecovacs account the robot is registered to**.
* The Ecovacs cloud and your internet connection must be up. If not, the app
  says "Nav savienojuma" and shows no invented state.

## What is different from the Home Assistant mode

| | Home Assistant mode | Direct mode |
|---|---|---|
| Needs Home Assistant | yes | **no** |
| Robot control, map, rooms, history | yes | yes (same library) |
| **Latvian spoken or phone announcements** | yes | **no** (they need Home Assistant's speakers and notifications; the Settings page says so) |
| Ecovacs login | done once in Home Assistant | done once with a command (below) |
| Python | 3.12+ | **3.14+** (the Docker image already has it) |
| Home Assistant entities to enable | Error, Last job | not needed; error codes and "job finished" come directly |

## Setup

1. In `.env` set `MODE=direct` and an `APP_PASSWORD`. You do **not** need `HA_URL` or `HA_TOKEN`. Do **not** put the Ecovacs password in `.env`.
2. Build, then do the **one-time login** in a terminal on the machine that runs the app:

   ```bash
   docker compose build
   docker compose run --rm backend python -m app.ecovacs_login
   ```

   It asks for:
   * the **country** of the Ecovacs account (two letters, for example `LV`). It must be the country the account was created in; a wrong country is the most common reason for a refused login;
   * the Ecovacs **e-mail** and **password** (the password is not shown and is **not stored**).

   If Ecovacs wants to verify this installation, it e-mails a **code**; type it in. A mistyped code may be re-entered three times.
   A refused login is reported once and **not retried**.

   On success it prints the robots on the account, for example
   `Robis | DEEBOT X9 PRO OMNI | class ilt3k8 | supported`. **Check that your robot says `supported`.**
   If it says "NOT supported", the library does not know that model yet. See below.
3. Start the app: `docker compose up -d`. Open `http://<pi-ip>:8080`.

Only Ecovacs' access token, the country and a random client ID are saved, in the Docker volume
(`/data/ecovacs_session.json`, readable only by the app). The app renews its session from that token
and never needs the password.

If you use a social login (Google/Apple) for Ecovacs, the account may have no password. Set one in the
Ecovacs Home app first. I have not verified this for Ecovacs.

## Several robots on one account

The app controls one robot. By default it takes the first by name. To choose, set `ECOVACS_DEVICE` in
`.env` to the robot's name (as shown by the login command) and restart.

## When something goes wrong

The app shows the reason on **Iestatījumi → Diagnostika un savienojums**.

| Message | Meaning and fix |
|---|---|
| "Nav pieslēgts Ecovacs kontam…" | No login saved yet. Run the login command. Then press **Savienoties vēlreiz** in Diagnostika (or restart). |
| "Ecovacs nepieņēma saglabāto pieteikšanos…" | Ecovacs rejected the saved token (for example it expired, or the password was changed). **Not retried automatically**, so the account cannot get locked. Run the login command again, then press **Savienoties vēlreiz**. How long a token stays valid is not documented; I have not measured it. |
| "Nav savienojuma ar Ecovacs serveri. Mēģina vēlreiz…" | Network or Ecovacs outage. Retries automatically, waiting up to 2 minutes between tries. |
| "Ecovacs mākonis nevar sazināties ar robotu." | The cloud is fine but the robot is off, asleep or off its Wi-Fi. Check the robot. |
| "Ecovacs bibliotēka vēl neatbalsta šo robota modeli." | The library does not recognise the robot's class code. Check `class` in Diagnostika. For the X9 PRO OMNI it should be `ilt3k8`. If the class differs, the robot's regional model needs support to be added to [deebot-client](https://github.com/DeebotUniverse/client.py/issues). |
| "Šis robots izmanto vecāku Ecovacs protokolu…" | An older robot that this app does not support. |

## Staying safe

* The app never repeats a rejected login. Only the one-time command ever sends your password, and only to Ecovacs.
* Anyone who can read `/data/ecovacs_session.json` can control your robot through your Ecovacs account. Keep the Pi and its backups private. To cut it off, change the Ecovacs password in the app (which invalidates tokens) and delete the file.
* Running both this app and Home Assistant's Ecovacs integration with the same account is possible, but each holds its own session; if you see sudden "rejected" messages, use only one.
