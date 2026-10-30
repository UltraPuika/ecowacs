import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { BigButton, Card } from "../components";
import { formatDateTime, timeAgo } from "../lv";
import type { CommandLog, LogEvent, Status } from "../types";

type Diag = Record<string, unknown> & { adapter?: Record<string, unknown> };

const MODE_LABEL: Record<Status["mode"], string> = {
  homeassistant: "Home Assistant",
  direct: "Tiešais savienojums ar Ecovacs (bez Home Assistant)",
  demo: "DEMO (nav īsts robots)",
};

export function Diagnostics({ status, onBack }: { status: Status; onBack: () => void }) {
  const [diag, setDiag] = useState<Diag | null>(null);
  const [log, setLog] = useState<{ events: LogEvent[]; commands: CommandLog[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [d, l] = await Promise.all([
        api.get<Diag>("/api/diagnostics"),
        api.get<{ events: LogEvent[]; commands: CommandLog[] }>("/api/events"),
      ]);
      setDiag(d);
      setLog(l);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Neizdevās ielādēt diagnostiku.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const rediscover = async () => {
    try {
      await api.post("/api/diagnostics/rediscover");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Neizdevās.");
    }
  };

  const a = (diag?.adapter ?? {}) as Record<string, unknown>;
  const recommended = (a.recommended_to_enable as string[] | undefined) ?? [];
  const { robot } = status;

  return (
    <div className="page">
      <BigButton label="← Atpakaļ" variant="plain" onClick={onBack} />
      {error && <p className="feedback feedback-error">{error}</p>}
      <Card title="Savienojums">
        <dl className="kv">
          <dt>Režīms</dt><dd>{MODE_LABEL[status.mode]}</dd>
          <dt>{status.mode === "direct" ? "Ecovacs serveris" : "Home Assistant"}</dt>
          <dd>{robot.backend_connected ? "savienots" : "nav savienojuma"}</dd>
          <dt>Robots</dt><dd>{robot.robot_available ? "sasniedzams" : "nav sasniedzams"}</dd>
          <dt>Pēdējā ziņa</dt><dd>{timeAgo(robot.last_update)} ({formatDateTime(robot.last_update)})</dd>
          <dt>Modelis</dt><dd>{robot.model ?? "nav zināms"}</dd>
          {robot.connection_problem && (<><dt>Problēma</dt><dd>{robot.connection_problem}</dd></>)}
          {typeof a.ha_version === "string" && (<><dt>HA versija</dt><dd>{a.ha_version}</dd></>)}
          {typeof a.vacuum_entity === "string" && (<><dt>Robota vienība</dt><dd>{a.vacuum_entity}</dd></>)}
          {typeof a.discovery_problem === "string" && (<><dt>Atrašana</dt><dd>{a.discovery_problem}</dd></>)}
          {typeof a.library === "string" && (<><dt>Bibliotēka</dt><dd>{a.library}</dd></>)}
          {status.mode === "direct" && (
            <>
              <dt>Pieteikšanās saglabāta</dt>
              <dd>{a.login_saved ? "jā" : "nē (palaidiet docker compose run --rm backend python -m app.ecovacs_login)"}</dd>
            </>
          )}
        </dl>
        {recommended.length > 0 && (
          <div className="feedback feedback-warn">
            Home Assistant ir izslēgtas šīs vienības. Ieslēdziet tās (Iestatījumi → Ierīces un pakalpojumi →
            Ecovacs → robots), lai redzētu kļūdu numurus un „tīrīšana pabeigta” paziņojumus:
            <ul>{recommended.map((e) => <li key={e}><code>{e}</code></li>)}</ul>
          </div>
        )}
        <div className="button-row">
          <BigButton
            label={status.mode === "direct" ? "Savienoties vēlreiz" : "Pārlasīt Home Assistant"}
            variant="secondary"
            onClick={() => void rediscover()}
          />
          <a className="big-button big-secondary" href="/api/diagnostics/export" download>
            Lejupielādēt diagnostiku
          </a>
        </div>
        <p className="help">Lejupielādētajā failā paroles, pilnvaras un e-pasta adreses ir aizstātas ar **REDACTED**.</p>
      </Card>

      <Card title="Iespējas">
        <ul className="caps">
          {Object.entries(robot.capabilities).map(([k, v]) => (
            <li key={k} className={v ? "yes" : "no"}>{v ? "✓" : "✗"} {k}</li>
          ))}
        </ul>
      </Card>

      {diag && a.entities !== undefined && (
        <Card title="Atrastās Home Assistant vienības">
          <pre className="pre">{JSON.stringify(a.entities ?? {}, null, 2)}</pre>
        </Card>
      )}

      <Card title="Pēdējie notikumi">
        {log?.events.length === 0 && <p className="muted">Nav notikumu.</p>}
        <ul className="log">
          {log?.events.slice(0, 50).map((e) => (
            <li key={e.id} className={`log-${e.level}`}>{formatDateTime(e.ts)} — {e.message}</li>
          ))}
        </ul>
      </Card>

      <Card title="Pēdējās komandas">
        <ul className="log">
          {log?.commands.slice(0, 50).map((c) => (
            <li key={c.id}>{formatDateTime(c.ts)} — {c.name}: {c.status} — {c.message}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
