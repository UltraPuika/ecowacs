# Installing on a Raspberry Pi 5

Tested target: Raspberry Pi OS 64-bit (Bookworm or newer) with Docker Engine and
the Compose plugin. Every image used (`python:3.13-slim`, `node:24-alpine`,
`nginx:1.28-alpine`) is published for `linux/arm64`.

> I could not run a Docker build in the development sandbox (no Docker daemon).
> The compose file passes `docker compose config`, and the backend and frontend
> pass their tests and production build outside Docker. Please report any
> problem from the first build on the Pi.

## 1. Prerequisites

- Home Assistant with the **Ecovacs** integration set up. See [HOME_ASSISTANT.md](HOME_ASSISTANT.md).
  *Or* skip Home Assistant and use [direct mode](DIRECT_MODE.md) (no spoken announcements).
- Docker on the Pi. If you run **Home Assistant OS**, the Pi has no general
  Docker host. In that case, run this app on another always-on Linux machine,
  or install HA as a container next to it.

If Docker is not installed yet:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # log out and back in afterwards
docker compose version
```

## 2. Install

```bash
git clone <this repository> deebot-lv
cd deebot-lv
cp .env.example .env
nano .env
```

Fill in at least these settings:

| Setting | Example | Notes |
|---|---|---|
| `HA_URL` | `http://192.168.1.10:8123` | Use the Pi's LAN IP even if HA runs on the same Pi. Inside a container, `localhost` means the container itself. |
| `HA_TOKEN` | `eyJ…` | HA → profile → Security → Long-lived access tokens |
| `APP_PASSWORD` | anything, at least 6 characters | Your parents type this once per phone |

Then start the app:

```bash
docker compose up -d --build
docker compose ps        # both services should become "healthy"
docker compose logs -f backend
```

Open `http://<pi-ip>:8080`. To use a different port, set `APP_PORT`.

## 3. Install the app on an Android phone (PWA)

1. Connect the phone to the **home Wi-Fi**.
2. Open **Chrome** and go to `http://<pi-ip>:8080`.
3. Log in with `APP_PASSWORD`. The login lasts 180 days (`SESSION_DAYS`).
4. Tap **⋮ → Add to Home screen** (Latvian Chrome: **"Pievienot sākuma ekrānam"**),
   then **Install**.
5. A "Robots" icon appears on the home screen and opens full-screen.

Note about plain `http://`: Chrome adds a home-screen shortcut that opens the
app full-screen, but the offline service worker only runs on HTTPS. The app
does not need it, because robot data is never cached. If you want the full PWA
behaviour, put the app behind HTTPS (for example the HA "NGINX" add-on or Caddy
with a local certificate) and set `SECURE_COOKIES=true`.

Tip: give the Pi a fixed IP address (a DHCP reservation in your router), so the
address on the phone stays valid.

## 4. Updating

```bash
cd deebot-lv
git pull
docker compose up -d --build
docker image prune -f
```

Settings, history and the login key live in the Docker volume `deebot-data`,
so updates keep them. To back them up:

```bash
docker run --rm -v deebot-lv_deebot-data:/d -v "$PWD":/b alpine tar czf /b/deebot-data.tgz -C /d .
```

## 5. Security notes

- The app is reachable only on your LAN. **Do not forward port 8080 on your router.**
  For remote access, use a VPN such as WireGuard or Tailscale.
- Only the frontend container publishes a port. The backend is internal.
- The backend never receives your Ecovacs password. It holds only the HA token,
  in `.env`, which you should keep private: run `chmod 600 .env`.
- Logs and diagnostic exports replace tokens, passwords and e-mail addresses with `**REDACTED**`.

## 6. Uninstall

```bash
docker compose down        # keep data
docker compose down -v     # also delete settings and history
```
