import { useState } from "react";
import { BigButton, Card, ConfirmDialog, FeedbackBox, useCommand } from "../components";
import { Icon } from "../icons";
import { activityText, formatMinutes, STATION, T, timeAgo, WORK_MODE } from "../lv";
import type { Status } from "../types";

interface Props {
  status: Status;
  onChooseRooms: () => void;
}

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

export function Home({ status, onChooseRooms }: Props) {
  const { robot, freshness, current_session } = status;
  const { run, busy, feedback } = useCommand();
  const [confirmStop, setConfirmStop] = useState(false);
  const caps = robot.capabilities;
  const online = robot.backend_connected;
  const disabled = !online || busy !== null;
  const rooms = current_session?.kind === "rooms" ? current_session.rooms : [];
  const stateClass = !online || !robot.robot_available ? "state-unknown" : COLOR[robot.activity];
  const active = robot.activity;

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

      <FeedbackBox feedback={feedback} />

      <div className="button-stack">
        {(active === "docked" || active === "idle" || active === "returning" || active === "unknown") && (
          <>
            <BigButton
              label={T.start}
              icon="play"
              busy={busy === "start"}
              disabled={disabled || !caps.start}
              onClick={() => void run("start")}
            />
            {caps.clean_rooms && (
              <BigButton label={T.chooseRooms} variant="secondary" icon="rooms" disabled={!online} onClick={onChooseRooms} />
            )}
          </>
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
