import { useEffect, useState } from "react";
import { BigButton, Card, ConfirmDialog, FeedbackBox, Toggle, useCommand } from "../components";
import { Icon } from "../icons";
import { activityText, formatMinutes, STATION, T, timeAgo, WORK_MODE } from "../lv";
import { zoneToRobot, type Rect } from "../mapGeometry";
import { loadShowCarpets, mapImageUrl, MapView, useMapMeta } from "../MapView";
import type { Status } from "../types";

interface Props {
  status: Status;
}

type Mode = "all" | "rooms" | "zone";

const COLOR: Record<string, string> = {
  cleaning: "state-active",
  paused: "state-paused",
  returning: "state-active",
  docked: "state-ok",
  idle: "state-ok",
  error: "state-error",
  unknown: "state-unknown",
};

/** Decorative picture for the status card (purely visual, hidden from screen readers). */
const STATE_ICON: Record<string, string> = {
  cleaning: "robot",
  paused: "pause",
  returning: "home",
  docked: "bolt",
  idle: "check",
  error: "alert",
  unknown: "robot",
};

export function Home({ status }: Props) {
  const { robot, freshness, current_session } = status;
  const { run, busy, feedback } = useCommand();
  const [confirmStop, setConfirmStop] = useState(false);
  const caps = robot.capabilities;
  const online = robot.backend_connected;
  const disabled = !online || busy !== null;
  const rooms = current_session?.kind === "rooms" ? current_session.rooms : [];
  const stateClass = !online || !robot.robot_available ? "state-unknown" : COLOR[robot.activity];
  const active = robot.activity;

  const { meta } = useMapMeta(robot.map_updated);
  const [imageFailed, setImageFailed] = useState(false);
  const [mode, setMode] = useState<Mode>("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [twice, setTwice] = useState(false);
  const [zone, setZone] = useState<Rect | null>(null);

  useEffect(() => setImageFailed(false), [robot.map_updated]);
  // Forget selections for rooms that no longer exist (e.g. map changed).
  useEffect(() => {
    const ids = new Set(robot.rooms.map((r) => r.id));
    setSelected((prev) => prev.filter((id) => ids.has(id)));
  }, [robot.rooms]);

  const box = meta?.available ? meta.view_box ?? null : null;
  const rotation = meta?.zone_rotation ?? null;
  const canRooms = Boolean(caps.clean_rooms && robot.rooms.length > 0);
  const canZone = Boolean(caps.clean_zone && box && rotation !== null);
  const activeMode: Mode = (mode === "rooms" && !canRooms) || (mode === "zone" && !canZone) ? "all" : mode;
  const idle = active === "docked" || active === "idle" || active === "returning" || active === "unknown";
  const hasRoomShapes = rotation !== null && robot.rooms.some((r) => (r.outline?.length ?? 0) >= 3);

  const toggleRoom = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id]));

  const chooseMode = (next: Mode) => {
    if (next === "zone" && !zone && box) {
      const side = Math.min(box[2], box[3]) * 0.3;
      setZone({ x: box[0] + box[2] / 2 - side / 2, y: box[1] + box[3] / 2 - side / 2, w: side, h: side });
    }
    setMode(next);
  };

  const modes: { id: Mode; label: string; icon: string; show: boolean }[] = [
    { id: "all", label: "Visa māja", icon: "home", show: true },
    { id: "rooms", label: "Telpas", icon: "rooms", show: canRooms },
    { id: "zone", label: "Zona", icon: "zone", show: canZone },
  ];
  const visibleModes = modes.filter((m) => m.show);

  return (
    <div className="page">
      <Card className={`status-card ${stateClass}`}>
        <div className="status-head">
          <span className="status-icon" aria-hidden="true">
            <Icon name={stateClass === "state-unknown" ? "offline" : STATE_ICON[active] ?? "robot"} />
          </span>
          <div className="status-text">
            <p className="status-title" data-testid="activity">
              {activityText(robot, rooms)}
            </p>
            {robot.station_state && robot.station_state !== "idle" && (
              <p className="status-sub">{STATION[robot.station_state] ?? robot.station_state}</p>
            )}
          </div>
        </div>
        <div className="battery" aria-label={`${T.battery}: ${robot.battery ?? "nav zināms"}%`}>
          <span className="battery-label">{T.battery}</span>
          <span className="battery-value">{robot.battery !== null ? `${robot.battery}%` : "—"}</span>
          <span className="battery-bar">
            <span
              className={`battery-fill ${robot.battery !== null && robot.battery < 20 ? "low" : ""}`}
              style={{ width: `${robot.battery ?? 0}%` }}
            />
          </span>
        </div>
        <p className="updated">
          {T.lastUpdate}: <strong>{timeAgo(robot.last_update)}</strong>
        </p>
      </Card>

      {robot.error && (
        <Card className="error-card">
          <h2>{robot.error.title}</h2>
          <p>{robot.error.explanation}</p>
          <p>
            <strong>{T.whatToDo}</strong> {robot.error.action}
          </p>
          {robot.error.code > 0 && <p className="muted">Kļūdas kods: {robot.error.code}</p>}
        </Card>
      )}

      {(caps.map || canRooms) && (
        <section className="map-card" aria-label="Karte">
          {!caps.map ? null : box && !imageFailed ? (
            <MapView
              src={mapImageUrl(robot.map_updated, loadShowCarpets())}
              viewBox={box}
              rotation={rotation}
              label="Robota karte. Velciet ar pirkstu, lai pārvietotu, savelciet ar diviem pirkstiem, lai tuvinātu."
              rooms={robot.rooms}
              selectedRooms={activeMode === "rooms" ? selected : []}
              onToggleRoom={activeMode === "rooms" ? toggleRoom : undefined}
              zone={activeMode === "zone" ? zone : null}
              onZoneChange={activeMode === "zone" ? setZone : undefined}
              onImageError={() => setImageFailed(true)}
            />
          ) : (
            <div className="map-empty">
              <Icon name="map" />
              <span>
                {imageFailed
                  ? "Neizdevās parādīt karti."
                  : meta && !meta.available
                    ? "Robots vēl nav atsūtījis karti."
                    : "Ielādē karti…"}
              </span>
            </div>
          )}

          {idle && visibleModes.length > 1 && (
            <div className="segmented" role="tablist" aria-label="Ko tīrīt">
              {visibleModes.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  role="tab"
                  aria-selected={activeMode === m.id}
                  className={activeMode === m.id ? "active" : ""}
                  onClick={() => chooseMode(m.id)}
                >
                  <Icon name={m.icon} />
                  <span>{m.label}</span>
                </button>
              ))}
            </div>
          )}

          {idle && activeMode === "rooms" && (
            <div className="mode-panel">
              <p className="muted">
                {hasRoomShapes ? "Pieskarieties telpām kartē vai sarakstā." : "Izvēlieties telpas, kuras tīrīt."}
              </p>
              <div className="room-chips">
                {robot.rooms.map((room) => {
                  const order = selected.indexOf(room.id) + 1;
                  return (
                    <button
                      key={room.id}
                      type="button"
                      className={`chip ${order ? "selected" : ""}`}
                      aria-pressed={order > 0}
                      onClick={() => toggleRoom(room.id)}
                    >
                      {order > 0 && (
                        <span className="chip-badge" aria-hidden="true">
                          {order}
                        </span>
                      )}
                      {room.name}
                    </button>
                  );
                })}
              </div>
              <Toggle label={T.cleanTwice} checked={twice} onChange={setTwice} />
            </div>
          )}

          {idle && activeMode === "zone" && (
            <div className="mode-panel">
              <p className="muted">Pārvelciet zilo laukumu uz vietu, kuru tīrīt. Velkot stūrus, maina izmēru.</p>
              <Toggle label={T.cleanTwice} checked={twice} onChange={setTwice} />
            </div>
          )}
        </section>
      )}

      <FeedbackBox feedback={feedback} />

      <div className="button-stack">
        {idle && activeMode === "all" && (
          <BigButton
            label={T.start}
            icon="play"
            busy={busy === "start"}
            disabled={disabled || !caps.start}
            onClick={() => void run("start")}
          />
        )}
        {idle && activeMode === "rooms" && (
          <BigButton
            label={T.cleanSelected(selected.length)}
            icon="play"
            busy={busy === "clean_rooms"}
            disabled={disabled || selected.length === 0}
            onClick={() => void run("clean_rooms", { rooms: selected, cleanings: twice ? 2 : 1 })}
          />
        )}
        {idle && activeMode === "zone" && zone && rotation !== null && (
          <BigButton
            label="Tīrīt zonu"
            icon="play"
            busy={busy === "clean_zone"}
            disabled={disabled}
            onClick={() =>
              void run("clean_zone", { coordinates: zoneToRobot(zone, rotation), cleanings: twice ? 2 : 1 })
            }
          />
        )}
        {active === "cleaning" && (
          <BigButton
            label={T.pause}
            icon="pause"
            busy={busy === "pause"}
            disabled={disabled || !caps.pause}
            onClick={() => void run("pause")}
          />
        )}
        {(active === "paused" || active === "error") && (
          <BigButton
            label={T.resume}
            icon="play"
            busy={busy === "resume"}
            disabled={disabled || !caps.start}
            onClick={() => void run("resume")}
          />
        )}
        {(active === "cleaning" || active === "paused" || active === "returning" || active === "error") && (
          <BigButton
            label={T.stop}
            icon="stop"
            variant="danger"
            busy={busy === "stop"}
            disabled={disabled || !caps.stop}
            onClick={() => setConfirmStop(true)}
          />
        )}
        {active !== "docked" && active !== "returning" && (
          <BigButton
            label={T.returnHome}
            icon="home"
            variant="secondary"
            busy={busy === "return_to_base"}
            disabled={disabled || !caps.return_to_base}
            onClick={() => void run("return_to_base")}
          />
        )}
      </div>

      {caps.work_mode && robot.work_mode_options.length > 0 && (
        <Card title={T.mode}>
          <div className="choice-list" role="radiogroup" aria-label={T.mode}>
            {robot.work_mode_options.map((mode) => (
              <button
                key={mode}
                type="button"
                role="radio"
                aria-checked={robot.work_mode === mode}
                className={`choice ${robot.work_mode === mode ? "selected" : ""}`}
                disabled={disabled}
                onClick={() => void run("set_work_mode", { value: mode })}
              >
                {WORK_MODE[mode] ?? mode}
              </button>
            ))}
          </div>
        </Card>
      )}

      {(robot.last_clean_area !== null || robot.last_clean_minutes !== null) && (
        <Card title={T.lastClean}>
          <p>
            Notīrīti <strong>{robot.last_clean_area ?? "—"} m²</strong>, laiks{" "}
            <strong>{formatMinutes(robot.last_clean_minutes)}</strong>
          </p>
        </Card>
      )}

      {caps.locate && (
        <BigButton
          label={T.locate}
          variant="plain"
          icon="sound"
          busy={busy === "locate"}
          disabled={disabled}
          onClick={() => void run("locate")}
        />
      )}

      {freshness.stale && <p className="muted center">{freshness.reason}</p>}

      {confirmStop && (
        <ConfirmDialog
          title={T.confirmStopTitle}
          text={T.confirmStopText}
          confirmLabel={T.stop}
          danger
          onCancel={() => setConfirmStop(false)}
          onConfirm={() => {
            setConfirmStop(false);
            void run("stop");
          }}
        />
      )}
    </div>
  );
}
