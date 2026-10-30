# Prompt for the local real-robot test session

Start Claude Code on **your own computer** (any computer with internet, Docker or `uv`, and Node 22+):

```bash
git clone -b claude/charming-allen-cx7lq0 https://github.com/UltraPuika/ecowacs.git
cd ecowacs && claude
```

Be physically near the robot, with its area clear. Then paste everything inside the box below.

```text
You are testing a Latvian robot-vacuum control app against my REAL ECOVACS DEEBOT X9 PRO OMNI, which has
never been done before. Everything in this repo was built and tested only with mocks. Your job is to find
out what really works, fix what does not, and report honestly.

## Read first
README.md, docs/DIRECT_MODE.md, docs/CAPABILITY_AUDIT.md, docs/MAP_AND_CARPET_LIMITATIONS.md,
backend/app/adapters/direct.py (the Ecovacs cloud adapter), backend/app/commands.py (command safety).
The robot is controlled through the Ecovacs CLOUD (there is no local/IP connection) with deebot-client 18.7.0
(needs Python 3.14; the Docker image has it). Use MODE=direct (no Home Assistant).

## Hard safety rules (do not break these)
1. NEVER ask me for, read, print, log or store my Ecovacs password, e-mail or verification code. I type them
   myself in a SEPARATE terminal window. Tell me the exact command to run there; do not run the login for me.
   Never read or print backend data/ecovacs_session.json, .env or any token. Never commit them.
2. Make at most ONE login attempt. If it is refused, stop and tell me; do not retry (account lockout risk).
3. Anything that makes the robot MOVE (start, pause, resume, stop, return to dock, room/zone clean) needs my
   explicit "yes" for that specific command, asked right before you do it, with what will happen. Harmless
   commands (locate sound) also get a heads-up. Reads are fine.
4. Never delete or rebuild the map, factory reset, flash firmware, touch voice packs, or try to change
   carpet detection. The app has no such controls on purpose; do not add them.
5. Before changing any robot setting (volume, child lock, carpet boost, water, clean count), record the
   original value, tell me, and restore it afterwards.
6. No customer personal data in anything you write or commit: no e-mails, names, addresses, serial/device
   IDs, tokens. Robot model and class code are fine. Use the app's redacted diagnostics export.
7. Do not create a pull request. Commit to the current branch only after tests pass, and ask before pushing.

## Setup (do this first, tell me results)
- Backend: cd backend && uv venv --python 3.14 && uv pip install -r requirements-dev.txt
  then: ruff check . && python -m pytest   (expect all green; direct-mode tests use the real library)
- Frontend: cd frontend && npm ci && npm test && npm run build
- Docker: cp .env.example .env ; set MODE=direct and APP_PASSWORD=<something>; docker compose build.
  The Docker images were NEVER built before (no Docker where they were written). Fix any build problem.
- Then ask me to run in a separate terminal:  docker compose run --rm backend python -m app.ecovacs_login
  (country = two letters of the Ecovacs account's country; it asks for e-mail, password, maybe an e-mail code)
  and tell you ONLY the robot line it prints (model | class | supported). Then docker compose up -d.

## Things the code ASSUMES but nobody has verified. Check each against the real robot and record the result
A. The robot's class is ilt3k8 and the library lists it as "supported" (if not, stop and report the class).
B. The saved login renews itself without the password (we do not know the token lifetime).
C. Events arrive and are mapped correctly: state, battery %, fan speed, work mode, rooms (ids + names),
   maps/active map, station state, error codes, volume/child lock/carpet boost/water/clean count, last
   clean area (m2) and time (library gives seconds; we show minutes).
D. "Last update" really stays fresh on a docked, idle robot (a heartbeat asks for the battery every 2 min;
   it relies on the library returning a non-empty result on success). Watch for false "stale" warnings.
E. deebot-client's execute_command never raises; failure = empty result. Confirm real successful commands
   return non-empty, and see what happens when the robot is unreachable.
F. Map: get_svg_map renders; does it contain carpet pixels (Karte page says found / none / no layer)?
   Are robot position, charger, trace, virtual walls drawn? Does "Atjaunot karti" refresh it?
G. Room cleaning sends ids as a LIST (a string would be split per character). Confirm the CORRECT room is
   cleaned, including a two-digit id if you have one. Zone cleaning (custom_area) coordinates: find out
   what coordinate system the robot expects; do not pretend it works if it does not.
H. The 25 s verification wait (VERIFY_TIMEOUT) is enough for start/pause/stop/return; note real latencies.
I. Error codes the robot actually reports have a sensible Latvian text (backend/app/errors_lv.py).

## Test plan (stop and ask me before each motion step)
1. Read-only: status, battery, rooms, maps, map image, diagnostics page, settings values. Compare with the
   official Ecovacs app that I can show you. Screenshot the UI with Playwright if useful.
2. Harmless: "Kur ir robots?" (locate sound).
3. Motion, one at a time, with my yes each: Sākt tīrīšanu -> Pauzēt -> Turpināt -> Apturēt -> Atgriezties uz
   staciju. Check the honest feedback ("confirmed" vs "sent but not confirmed") and the history entry.
4. One small room only, via the Karte page. Check the right room, and that history records the room name.
5. Settings round trips with restore (rule 5).
6. If I agree: switch the robot off / unplug its Wi-Fi briefly and check the app says "no connection to the
   robot" and never shows old data as current; then check it recovers.
7. Optional: install the APK from the latest GitHub release on my Android phone (Settings of the app asks
   for the server address) and check the same screens.

## Fix what breaks
Write a failing test first when you can (backend/tests, real-library fixtures are in tests/test_direct.py),
fix, rerun ruff + pytest + vitest + build. Keep changes small and in the existing style.

## Report
Write docs/REAL_DEVICE_TEST_REPORT.md: a table of every feature and assumption A-I with
WORKED / FAILED / NOT TESTED, the evidence (what you saw), and what you changed. Update the statuses in
docs/CAPABILITY_AUDIT.md only for things you actually verified, with the date. Do not claim anything that
was not tested on the real robot. List remaining problems and what I should do next.
```
