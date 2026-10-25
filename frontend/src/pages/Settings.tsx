import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { BigButton, Card, FeedbackBox, Toggle, useCommand, type Feedback } from "../components";
import { FAN_SPEED, SETTING, T } from "../lv";
import type { AnnouncementSettings, Setting, SpeechTargets, Status } from "../types";
import { Diagnostics } from "./Diagnostics";

const EVENT_LABELS: Record<string, string> = {
  started: "Robots sāk tīrīt",
  finished: "Tīrīšana pabeigta",
  returning: "Robots brauc uz staciju",
  error: "Robotam vajag palīdzību (kļūda, iestrēdzis)",
  command_failed: "Neizdevās sākt tīrīšanu",
};

function NumberSetting({ setting, disabled, onSave }: {
  setting: Setting; disabled: boolean; onSave: (v: number) => void;
}) {
  const [value, setValue] = useState(Number(setting.value ?? 0));
  useEffect(() => setValue(Number(setting.value ?? 0)), [setting.value]);
  const meta = SETTING[setting.key] ?? { label: setting.key };
  const changed = value !== Number(setting.value);
  return (
    <div className="number-setting">
      <label>
        <span className="toggle-label">{meta.label}: <strong>{value}</strong></span>
        <input
          type="range"
          min={setting.min ?? 0}
          max={setting.max ?? 100}
          step={setting.step ?? 1}
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(Number(e.target.value))}
        />
      </label>
      {changed && (
        <button type="button" className="small-button" disabled={disabled} onClick={() => onSave(value)}>
          {T.save}
        </button>
      )}
    </div>
  );
}

function Announcements() {
  const [settings, setSettings] = useState<AnnouncementSettings | null>(null);
  const [targets, setTargets] = useState<SpeechTargets | null>(null);
  const [targetsError, setTargetsError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  useEffect(() => {
    api.get<AnnouncementSettings>("/api/announcements").then(setSettings).catch(() => undefined);
    api
      .get<SpeechTargets>("/api/announcements/targets")
      .then(setTargets)
      .catch((err) => setTargetsError(err instanceof ApiError ? err.message : "Neizdevās."));
  }, []);

  if (!settings) return <p>{T.loading}</p>;
  const update = (patch: Partial<AnnouncementSettings>) => setSettings({ ...settings, ...patch });

  const save = async () => {
    try {
      setSettings(await api.put<AnnouncementSettings>("/api/announcements", settings));
      setFeedback({ kind: "ok", text: T.saved });
    } catch (err) {
      setFeedback({ kind: "error", text: err instanceof ApiError ? err.message : "Neizdevās saglabāt." });
    }
  };
  const test = async () => {
    setFeedback({ kind: "pending", text: "Sūta pārbaudes paziņojumu…" });
    try {
      const r = await api.post<{ ok: boolean; problems: string[] }>("/api/announcements/test", settings);
      setFeedback(
        r.ok
          ? { kind: "ok", text: "Paziņojums nosūtīts. Vai to dzirdējāt?" }
          : { kind: "error", text: r.problems.join(" ") },
      );
    } catch (err) {
      setFeedback({ kind: "error", text: err instanceof ApiError ? err.message : "Neizdevās." });
    }
  };

  const select = (label: string, value: string, options: string[] | undefined, key: keyof AnnouncementSettings) => (
    <label className="field">
      {label}
      <select value={value} onChange={(e) => update({ [key]: e.target.value } as Partial<AnnouncementSettings>)}>
        <option value="">— nav izvēlēts —</option>
        {(options ?? []).map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
        {value && !(options ?? []).includes(value) && <option value={value}>{value}</option>}
      </select>
    </label>
  );

  return (
    <>
      <Toggle label="Ieslēgt paziņojumus latviski" checked={settings.enabled} onChange={(v) => update({ enabled: v })} />
      <p className="help">
        Robots pats latviski nerunā. Paziņojumus izrunā Home Assistant skaļrunis (piemēram, ar bezmaksas
        Piper balsi „lv_LV-aivars”) vai tie atnāk kā ziņa tālrunī.
      </p>
      {targetsError && <p className="feedback feedback-warn">{targetsError}</p>}
      {select("Runas balss (TTS)", settings.tts_entity, targets?.tts_entities, "tts_entity")}
      {select("Skaļrunis", settings.media_player, targets?.media_players, "media_player")}
      <label className="field">
        Skaļums: {settings.volume === null ? "nemainīt" : `${Math.round(settings.volume * 100)}%`}
        <input
          type="range" min={0} max={100} step={5}
          value={Math.round((settings.volume ?? 0.5) * 100)}
          onChange={(e) => update({ volume: Number(e.target.value) / 100 })}
        />
      </label>
      {settings.volume !== null && (
        <button type="button" className="small-button" onClick={() => update({ volume: null })}>
          Nemainīt skaļruņa skaļumu
        </button>
      )}
      <label className="field">
        Valodas kods (neobligāti, piem. „lv” vai „lv_LV”)
        <input value={settings.language} onChange={(e) => update({ language: e.target.value })} />
      </label>
      {select("Ziņa tālrunī (neobligāti)", settings.notify_service, targets?.notify_services, "notify_service")}
      <fieldset className="events">
        <legend>Par ko paziņot</legend>
        {Object.entries(EVENT_LABELS).map(([key, label]) => (
          <Toggle
            key={key}
            label={label}
            checked={settings.events[key] ?? false}
            onChange={(v) => update({ events: { ...settings.events, [key]: v } })}
          />
        ))}
      </fieldset>
      <p className="help">
        „Tīrīšana pabeigta” darbojas tikai tad, ja Home Assistant ir ieslēgta robota vienība „Last job”.
        Viens un tas pats paziņojums netiek atkārtots 5 minūšu laikā.
      </p>
      <FeedbackBox feedback={feedback} />
      <div className="button-row">
        <BigButton label={T.save} onClick={() => void save()} />
        <BigButton label="Pārbaudīt" variant="secondary" onClick={() => void test()} />
      </div>
    </>
  );
}

export function Settings({ status, onLogout, authRequired }: {
  status: Status; onLogout: () => void; authRequired: boolean;
}) {
  const { robot } = status;
  const { run, busy, feedback } = useCommand();
  const [showDiag, setShowDiag] = useState(false);
  const disabled = !robot.backend_connected || busy !== null;
  const settings = Object.values(robot.settings);
  const setSetting = useCallback(
    (key: string, value: boolean | number) => void run("set_setting", { key, value }),
    [run],
  );

  if (showDiag) return <Diagnostics status={status} onBack={() => setShowDiag(false)} />;

  return (
    <div className="page">
      <FeedbackBox feedback={feedback} />
      <Card title="Tīrīšanas iestatījumi">
        {robot.capabilities.fan_speed && robot.fan_speed_options.length > 0 && (
          <label className="field">
            Sūkšanas jauda
            <select
              value={robot.fan_speed ?? ""}
              disabled={disabled}
              onChange={(e) => void run("set_fan_speed", { value: e.target.value })}
            >
              {robot.fan_speed_options.map((o) => (
                <option key={o} value={o}>{FAN_SPEED[o] ?? o}</option>
              ))}
            </select>
          </label>
        )}
        {settings.filter((s) => s.kind === "switch").map((s) => (
          <Toggle
            key={s.key}
            label={SETTING[s.key]?.label ?? s.key}
            help={SETTING[s.key]?.help}
            checked={Boolean(s.value)}
            disabled={disabled}
            onChange={(v) => setSetting(s.key, v)}
          />
        ))}
        {settings.filter((s) => s.kind === "number").map((s) => (
          <NumberSetting key={s.key} setting={s} disabled={disabled} onSave={(v) => setSetting(s.key, v)} />
        ))}
        {settings.length === 0 && (
          <p className="muted">Robots nav atsūtījis iestatījumus vai Home Assistant tās vienības ir izslēgtas.</p>
        )}
        {robot.capabilities.empty_dustbin && (
          <BigButton
            label="Iztukšot putekļus stacijā"
            variant="secondary"
            busy={busy === "empty_dustbin"}
            disabled={disabled || robot.activity !== "docked"}
            onClick={() => void run("empty_dustbin")}
          />
        )}
        <p className="help">
          Paklāju atpazīšanas jutība, balss valoda un kartes labošana šeit nav pieejama — to var mainīt tikai
          Ecovacs Home lietotnē.
        </p>
      </Card>

      <Card title="Paziņojumi latviski">
        <Announcements />
      </Card>

      <Card title="Papildu">
        <BigButton label="Diagnostika un savienojums" variant="secondary" onClick={() => setShowDiag(true)} />
        {authRequired && <BigButton label={T.logout} variant="plain" onClick={onLogout} />}
      </Card>
    </div>
  );
}
