import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { BigButton, Card, ConfirmDialog } from "../components";
import { formatDateTime, formatMinutes, joinLv, RESULT } from "../lv";
import type { Session } from "../types";

function kindText(s: Session): string {
  if (s.kind === "rooms") return `Telpas: ${joinLv(s.rooms)}`;
  if (s.kind === "zone") return "Zona";
  return "Visa māja";
}

export function History() {
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);

  const load = useCallback(async () => {
    try {
      setSessions((await api.get<{ sessions: Session[] }>("/api/history")).sessions);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Neizdevās ielādēt vēsturi.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const clear = async () => {
    setConfirm(false);
    try {
      await api.del("/api/history", { confirm: true });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Neizdevās notīrīt vēsturi.");
    }
  };

  return (
    <div className="page">
      <p className="help">
        Šo vēsturi pieraksta pati lietotne. Tīrīšanas, kas notika, kamēr lietotne nedarbojās, šeit neparādās.
        Platību un laiku ziņo robots.
      </p>
      {error && <p className="feedback feedback-error">{error}</p>}
      {sessions === null && !error && <p>Ielādē…</p>}
      {sessions?.length === 0 && <Card><p>Vēl nav nevienas tīrīšanas.</p></Card>}
      {sessions?.map((s) => (
        <Card key={s.id} className="history-item">
          <h3>{formatDateTime(s.started_at)}</h3>
          <p><strong>{kindText(s)}</strong></p>
          <p>
            {s.ended_at === null ? "Notiek" : RESULT[s.result ?? "unknown"] ?? s.result}
            {" · "}
            {s.area_m2 !== null ? `${s.area_m2} m²` : "— m²"}
            {" · "}
            {formatMinutes(s.minutes)}
          </p>
          <p className="muted">
            {s.started_by === "app" ? "Sākts no šīs lietotnes" : "Sākts citur (uz robota, grafikā vai Ecovacs lietotnē)"}
          </p>
        </Card>
      ))}
      {sessions && sessions.length > 0 && (
        <BigButton label="Notīrīt vēsturi" variant="plain" onClick={() => setConfirm(true)} />
      )}
      {confirm && (
        <ConfirmDialog
          title="Notīrīt vēsturi?"
          text="Tiks izdzēsts šīs lietotnes tīrīšanu, notikumu un komandu saraksts. Robotu un tā karti tas neietekmē."
          confirmLabel="Notīrīt"
          danger
          onCancel={() => setConfirm(false)}
          onConfirm={() => void clear()}
        />
      )}
    </div>
  );
}
