// All user-visible Latvian text in one place.
import type { Activity, Robot } from "./types";

export const T = {
  appName: "Robots",
  nav: { home: "Sākums", map: "Karte", history: "Tīrīšanas vēsture", settings: "Iestatījumi" },
  start: "Sākt tīrīšanu",
  pause: "Pauzēt",
  resume: "Turpināt",
  stop: "Apturēt",
  returnHome: "Atgriezties uz staciju",
  locate: "Kur ir robots?",
  chooseRooms: "Tīrīt tikai dažas telpas",
  cleanSelected: (n: number) => `Tīrīt izvēlētās telpas (${n})`,
  cleanTwice: "Tīrīt divas reizes",
  battery: "Akumulators",
  lastUpdate: "Pēdējā ziņa no robota",
  noConnectionRobot: "Nav savienojuma ar robotu",
  noConnectionServer: "Nav savienojuma ar lietotnes serveri",
  needsAttention: "Nepieciešama uzmanība",
  whatToDo: "Ko darīt:",
  demoBanner: "DEMO REŽĪMS — šis nav īsts robots. Visi dati ir izdomāti.",
  staleTitle: "Dati var būt novecojuši",
  sending: "Sūta komandu…",
  waiting: "Komanda nosūtīta. Gaidām, kad robots apstiprinās…",
  confirmStopTitle: "Apturēt tīrīšanu?",
  confirmStopText: "Robots pārtrauks tīrīt un paliks tur, kur atrodas.",
  yes: "Jā",
  cancel: "Atcelt",
  mode: "Tīrīšanas veids",
  lastClean: "Pēdējā tīrīšana",
  loginTitle: "Ieiet",
  password: "Parole",
  login: "Ieiet",
  logout: "Iziet",
  loading: "Ielādē…",
  save: "Saglabāt",
  saved: "Saglabāts.",
};

export const ACTIVITY: Record<Activity, string> = {
  cleaning: "Robots tīra",
  paused: "Tīrīšana nopauzēta",
  returning: "Robots atgriežas uz staciju",
  docked: "Robots ir stacijā",
  idle: "Robots stāv un gaida",
  error: "Nepieciešama uzmanība",
  unknown: "Stāvoklis nav zināms",
};

export function activityText(robot: Robot, cleaningRooms: string[] = []): string {
  if (!robot.backend_connected || !robot.robot_available) return T.noConnectionRobot;
  if (robot.activity === "cleaning" && cleaningRooms.length > 0) {
    return `Tīra: ${joinLv(cleaningRooms)}`;
  }
  if (robot.activity === "docked") {
    if (robot.battery !== null && robot.battery >= 100) return "Robots ir uzlādēts un gatavs";
    return "Robots uzlādējas";
  }
  return ACTIVITY[robot.activity];
}

export const FAN_SPEED: Record<string, string> = {
  quiet: "Klusā",
  normal: "Normālā",
  max: "Spēcīgā",
  max_plus: "Maksimālā",
};

export const WORK_MODE: Record<string, string> = {
  vacuum: "Tikai sūkt",
  vacuum_and_mop: "Sūkt un mazgāt",
  mop_after_vacuum: "Vispirms sūkt, tad mazgāt",
  mop: "Tikai mazgāt",
};

export const WATER_AMOUNT: Record<string, string> = {
  low: "Maz",
  medium: "Vidēji",
  high: "Daudz",
  ultrahigh: "Ļoti daudz",
};

export const MODE_LABEL: Record<string, string> = {
  ecovacs: "Ecovacs mākonis (tieši)",
  homeassistant: "Home Assistant",
  demo: "DEMO (nav īsts robots)",
};

export const STATION: Record<string, string> = {
  idle: "Stacija gaida",
  emptying_dustbin: "Stacija iztukšo putekļus",
  washing_mop: "Stacija mazgā mopus",
  drying_mop: "Stacija žāvē mopus",
};

export const SETTING: Record<string, { label: string; help?: string }> = {
  carpet_auto_fan_boost: {
    label: "Palielināt jaudu uz paklājiem",
    help: "Robots sūc stiprāk, kad uzbrauc uz paklāja. Tas nemaina to, kā robots atpazīst paklājus.",
  },
  continuous_cleaning: {
    label: "Turpināt tīrīšanu pēc uzlādes",
    help: "Ja akumulators beidzas, robots uzlādējas un pēc tam turpina tur, kur palika.",
  },
  child_lock: { label: "Bērnu slēdzene", help: "Bloķē pogas uz paša robota." },
  volume: { label: "Robota balss skaļums" },
  water_amount: { label: "Ūdens daudzums mazgājot" },
  clean_count: { label: "Cik reizes tīrīt katru vietu" },
};

export const RESULT: Record<string, string> = {
  finished: "Pabeigta",
  finished_with_warnings: "Pabeigta ar brīdinājumiem",
  manually_stopped: "Apturēta",
  unknown: "Beigas nav zināmas",
};

export const CONNECTION = {
  live: "Savienots",
  connecting: "Savienojas…",
  offline: "Nav savienojuma",
};

export function joinLv(names: string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} un ${names[names.length - 1]}`;
}

// "pirms" takes the genitive singular and the dative plural; numbers ending in 1 (not 11) are singular.
function unit(n: number, singular: string, plural: string): string {
  const single = n % 10 === 1 && n % 100 !== 11;
  return `${n} ${single ? singular : plural}`;
}

export function timeAgo(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "nav zināms";
  const seconds = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "tikko";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `pirms ${unit(minutes, "minūtes", "minūtēm")}`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `pirms ${unit(hours, "stundas", "stundām")}`;
  const days = Math.floor(hours / 24);
  return `pirms ${unit(days, "dienas", "dienām")}`;
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("lv-LV", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatMinutes(minutes: number | null): string {
  if (minutes === null || minutes === undefined) return "—";
  const m = Math.round(minutes);
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}
