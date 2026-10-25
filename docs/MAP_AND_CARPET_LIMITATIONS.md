# Map and carpet limitations

## What the map in this app is

The map is the **SVG image that `deebot-client` renders** inside Home Assistant
(`image.<robot>_map`). It shows:

- the floor plan, from either the robot's pixel map or its vector "MapInfo_V2" data,
- the robot (yellow circle) and charger position,
- the trace of the current or last job (white line),
- virtual walls and no-go zones (red) and no-mop zones (orange), if the robot sends them.

It is a **picture, not an editable map**. This app cannot move room borders,
draw or delete walls, rename rooms, or delete the map. No supported API exists
for any of that on the X9 PRO OMNI (see [CAPABILITY_AUDIT.md](CAPABILITY_AUDIT.md)).
Use the Ecovacs Home app for those tasks.

**"Atjaunot karti"** asks HA to download the map from the robot again. It does
**not** make the robot re-scan the house.

## Problem A: the robot skips areas

An alternative app **cannot override the robot's navigation**. The likely
causes, and what you can do about each:

| Possible cause | How to recognise it | What to do |
|---|---|---|
| Wrong active map (wrong floor) | "Aktīvā karte" name does not match the floor | Switch the map in the app (Karte → Stāvs / karte) or in the Ecovacs app |
| Old virtual wall or no-go zone | Red line or area where the robot does not go | Delete it in the Ecovacs Home app (Map → Virtual boundary) |
| Furniture remembered as an obstacle | Robot avoids a spot where furniture used to be | Clean that room on its own. Robots usually re-check obstacles during a job. If it persists, rebuild the map. |
| Wrong room segmentation | Room borders in the picture do not match the walls | Merge or split rooms in the Ecovacs app |
| Localization problem | Errors such as "Robots nesaprot, kur atrodas" (410/420/1062/1088), trace drawn outside walls | Start from the dock. If it repeats, rebuild the map. |
| Map corruption | Walls doubled or shifted | Rebuild the map in the Ecovacs app (this deletes rooms, walls and schedules) |
| Physical blockers | The trace stops at a threshold, cables or a rug fringe | Remove or raise the obstacle |

The **Karte → "Ja robots izlaiž vietas"** checklist in the app walks through
these steps in Latvian.

**"Uncleaned areas"**: the map shows the trace, and you can compare it with the
room shapes by eye. The app does **not** claim to detect missed areas
automatically, because the data available is not reliable enough to do that.

## Problem B: carpet-shaped regions

### What they are

`deebot-client` renders the robot's pixel map with a palette in which index 3 is
**"Carpet"** (`src/map/background_image.rs`). Carpet shapes are therefore part
of the robot's own surface classification in its saved map. The robot detects
them, stores them, and uses them to decide on suction boost and mop behaviour.

When the robot sends **vector (MapInfo_V2)** data instead, `deebot-client`
draws the vectors and skips the pixel image. The vector layers that might hold
carpets (types 3 and 4) are "unknown" to the library and are not drawn. Which
case applies to your X9 is **unverified**. The Map page tells you:

- "Paklāji šajā kartē ir atrasti" means carpet pixels exist and can be hidden.
- "…nav atzīmējis paklājus…" means there is a pixel map with no carpets.
- "…paklāju slānis nav pieejams…" means there is no pixel layer, so there is nothing to show or hide.

### Three separate things

| # | Capability | Possible here? |
|---|---|---|
| 1 | **Hide carpet shapes in this app's picture** | **Yes.** The "Rādīt / Slēpt paklājus kartē" toggle recolours carpet pixels to the floor colour in the image we display. Nothing is sent to the robot. The preference is stored only in that browser. |
| 2 | **Change carpet settings on the robot** | **Only "Palielināt jaudu uz paklājiem"** (carpet auto fan boost, on or off) |
| 3 | **Change how the robot detects or avoids carpets** | **No.** There is no API in `deebot-client` for any model. Only the Ecovacs Home app can change carpet detection, mop handling on carpets, or delete detected carpet areas. |

Hiding carpets in the picture **does not** stop the robot from recognising or
avoiding carpets. The app says this next to the toggle.

### Legitimate workarounds

- In the Ecovacs Home app, check the carpet settings (carpet detection and
  carpet cleaning strategy) and the per-area carpet editing your firmware offers.
- Use **no-mop zones** in the Ecovacs app for areas the robot must not mop.
- If a carpet has been removed and the robot still treats the area as carpet,
  let it clean that room again so it can re-detect the floor. If the area
  persists, rebuilding the map clears it.
- Do not modify the robot's firmware. This project deliberately avoids anything
  that could brick the robot.
