import { useEffect, useState } from "react";
import { BigButton, Card, ConfirmDialog, FeedbackBox, Toggle, useCommand } from "../components";
import { formatDateTime, timeAgo } from "../lv";
import { loadShowCarpets, mapImageUrl, MapView, saveShowCarpets, useMapMeta } from "../MapView";
import type { Status } from "../types";

export function MapPage({ status }: { status: Status }) {
  const { robot } = status;
  const caps = robot.capabilities;
  const { run, busy, feedback } = useCommand();
  const { meta, error: metaError, reload: loadMeta } = useMapMeta(robot.map_updated);
  const [version, setVersion] = useState(0);
  const [imageFailed, setImageFailed] = useState(false);
  const [showCarpets, setShowCarpets] = useState(loadShowCarpets);
  const [pendingMap, setPendingMap] = useState<string | null>(null);
  const [zone, setZone] = useState(["", "", "", ""]);

  useEffect(() => {
    setImageFailed(false);
  }, [version, robot.map_updated, showCarpets]);

  const toggleCarpets = (value: boolean) => {
    setShowCarpets(value);
    saveShowCarpets(value);
  };

  const refreshMap = async () => {
    const result = await run("refresh_map");
    if (result && (result.status === "done" || result.status === "confirmed")) {
      window.setTimeout(() => {
        setVersion((v) => v + 1);
        void loadMeta();
      }, 3000);
    }
  };

  const imageUrl = mapImageUrl(robot.map_updated, showCarpets, version);
  const disabled = !robot.backend_connected || busy !== null;
  const zoneNumbers = zone.map((z) => Number.parseInt(z, 10));
  const zoneValid = zone.every((z) => /^-?\d+$/.test(z.trim()));
  const box = meta?.view_box ?? null;

  return (
    <div className="page">
      <FeedbackBox feedback={feedback} />

      <Card title="Karte">
        <p>
          Aktīvā karte: <strong>{robot.active_map ?? "nav zināma"}</strong>
          <br />
          Karte atjaunota: <strong>{robot.map_updated ? timeAgo(robot.map_updated) : "nav zināms"}</strong>
          {robot.map_updated && <span className="muted"> ({formatDateTime(robot.map_updated)})</span>}
        </p>

        {metaError && <p className="feedback feedback-error">{metaError}</p>}
        {meta && !meta.available && (
          <p className="feedback feedback-warn">
            {meta.error ?? "Karte nav pieejama. Robots to vēl nav atsūtījis vai karte nav izveidota."}
          </p>
        )}
        {meta?.available && box && !imageFailed && (
          <>
            <MapView
              src={imageUrl}
              viewBox={box}
              rotation={meta.zone_rotation ?? null}
              label="Robota saglabātā karte"
              rooms={robot.rooms}
              onImageError={() => setImageFailed(true)}
            />
            <ul className="legend">
              <li><span className="swatch robot" /> zils aplis — robots, dzeltena adata — stacija</li>
              <li><span className="swatch trace" /> balta līnija — kur robots brauca šajā tīrīšanā</li>
              <li><span className="swatch wall" /> sarkans — virtuālā siena / aizliegtā zona</li>
              <li><span className="swatch nomop" /> oranžs — zona bez mazgāšanas</li>
            </ul>
          </>
        )}
        {imageFailed && <p className="feedback feedback-error">Neizdevās parādīt kartes attēlu.</p>}

        <BigButton
          label="Atjaunot karti"
          variant="secondary"
          icon="refresh"
          busy={busy === "refresh_map"}
          disabled={disabled || !caps.map}
          onClick={() => void refreshMap()}
        />
        <p className="help">
          Tas lejupielādē karti no robota vēlreiz. Robots netiek sūtīts no jauna izpētīt māju.
        </p>
      </Card>

      <Card title="Paklāji kartē">
        <Toggle
          label={showCarpets ? "Rādīt paklājus kartē" : "Slēpt paklājus kartē"}
          help="Maina tikai attēlu šajā lietotnē. Robots joprojām atpazīst paklājus un uzvedas tāpat kā iepriekš."
          checked={showCarpets}
          onChange={toggleCarpets}
        />
        <p className="muted" data-testid="carpet-status">
          {meta?.carpet_found === true && "Paklāji šajā kartē ir atrasti."}
          {meta?.carpet_found === false && "Šajā kartē robots nav atzīmējis paklājus, tāpēc slēpšana neko nemaina."}
          {meta?.available && (meta.carpet_found === null || meta.carpet_found === undefined) &&
            "Šai kartei paklāju slānis nav pieejams (robots sūta karti citā formātā), tāpēc tos nevar ne parādīt, ne paslēpt."}
        </p>
        <details>
          <summary>Kā mainīt to, kā robots izturas pret paklājiem?</summary>
          <p>
            Šī lietotne var tikai ieslēgt vai izslēgt „Palielināt jaudu uz paklājiem” (sadaļā Iestatījumi).
            Paklāju atpazīšanas jutību, paklāju apiešanu mazgājot un paklāju laukumu dzēšanu var mainīt
            tikai oficiālajā Ecovacs Home lietotnē. Ja robots nedrīkst mazgāt kādu vietu, izveidojiet tur
            „zonu bez mazgāšanas” Ecovacs Home lietotnē.
          </p>
        </details>
      </Card>

      {caps.active_map && robot.map_options.length > 1 && (
        <Card title="Stāvs / karte">
          <div className="choice-list">
            {robot.map_options.map((name) => (
              <button
                key={name}
                type="button"
                className={`choice ${robot.active_map === name ? "selected" : ""}`}
                disabled={disabled || robot.active_map === name}
                onClick={() => setPendingMap(name)}
              >
                {name}
              </button>
            ))}
          </div>
        </Card>
      )}

      <Card title="Ja robots izlaiž vietas">
        <details>
          <summary>Pārbaudes saraksts soli pa solim</summary>
          <ol className="steps">
            <li>Pārbaudiet, vai augšā ir pareizā <strong>aktīvā karte</strong> (pareizais stāvs).</li>
            <li>Nospiediet <strong>„Atjaunot karti”</strong> un apskatiet, vai telpu robežas atbilst mājai.</li>
            <li>
              Meklējiet kartē <strong>sarkanas</strong> līnijas vai laukumus — tās ir virtuālās sienas vai
              aizliegtās zonas. Ja tur, kur robots nebrauc, ir sarkana zona, izdzēsiet to Ecovacs Home lietotnē.
            </li>
            <li>
              Pēc tīrīšanas apskatiet <strong>baltu līniju</strong>, kur robots brauca. Ja kādā vietā līnijas nav,
              pārbaudiet, vai ceļu neaizšķērso vadi, sliekšņi vai mēbeles.
            </li>
            <li>
              Ja mēbeles ir pārvietotas, iztīriet konkrēto telpu atsevišķi (Sākums → „Telpas”). Robots kartē
              redz šķēršļus, kas tur bija iepriekšējā reizē.
            </li>
            <li>
              Ja karte ir acīmredzami nepareiza (sienas nobīdītas, telpas sajauktas), vienīgais drošais risinājums
              ir izveidot jaunu karti <strong>Ecovacs Home lietotnē</strong>: „Karte → Kartes pārvaldība”.
              Šī darbība izdzēš telpas, virtuālās sienas un grafikus. Šī lietotne karti nedzēš.
            </li>
          </ol>
          <p className="help">
            Šī lietotne nevar mainīt robota navigāciju. Tā tikai rāda robota karti un ļauj izvēlēties, ko tīrīt.
          </p>
        </details>
      </Card>

      {caps.clean_zone && meta?.zone_rotation == null && (
        <Card title="Papildu: zonas tīrīšana pēc koordinātām">
          <details>
            <summary>Tikai pieredzējušiem lietotājiem</summary>
            <p className="help">
              Ievadiet taisnstūri robota koordinātās (x1, y1, x2, y2). Šīs koordinātas nav redzamas kartes attēlā,
              tāpēc nepareizi skaitļi var likt robotam tīrīt citu vietu.
            </p>
            <div className="zone-grid">
              {["x1", "y1", "x2", "y2"].map((label, i) => (
                <label key={label}>
                  {label}
                  <input
                    inputMode="numeric"
                    value={zone[i]}
                    onChange={(e) => setZone((z) => z.map((v, j) => (j === i ? e.target.value : v)))}
                  />
                </label>
              ))}
            </div>
            <BigButton
              label="Tīrīt šo zonu"
              variant="secondary"
              busy={busy === "clean_zone"}
              disabled={disabled || !zoneValid}
              onClick={() => void run("clean_zone", { coordinates: zoneNumbers, cleanings: 1 })}
            />
          </details>
        </Card>
      )}

      {pendingMap && (
        <ConfirmDialog
          title="Mainīt aktīvo karti?"
          text={`Robots turpmāk izmantos karti „${pendingMap}”. Ja robots atrodas citā stāvā, tas tīrīs ar nepareizām robežām.`}
          confirmLabel="Mainīt"
          onCancel={() => setPendingMap(null)}
          onConfirm={() => {
            const name = pendingMap;
            setPendingMap(null);
            void run("set_active_map", { value: name });
          }}
        />
      )}
    </div>
  );
}
