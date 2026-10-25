export type Activity =
  | "cleaning"
  | "paused"
  | "returning"
  | "docked"
  | "idle"
  | "error"
  | "unknown";

export interface Room {
  id: string;
  name: string;
}

export interface ErrorInfo {
  code: number;
  title: string;
  explanation: string;
  action: string;
  original: string | null;
}

export interface Setting {
  key: string;
  kind: "switch" | "number" | "select";
  value: boolean | number | string | null;
  min: number | null;
  max: number | null;
  step: number | null;
  options: string[];
}

export interface Robot {
  backend_connected: boolean;
  robot_available: boolean;
  activity: Activity;
  battery: number | null;
  fan_speed: string | null;
  fan_speed_options: string[];
  work_mode: string | null;
  work_mode_options: string[];
  rooms: Room[];
  active_map: string | null;
  map_options: string[];
  map_updated: string | null;
  error: ErrorInfo | null;
  station_state: string | null;
  last_clean_area: number | null;
  last_clean_minutes: number | null;
  settings: Record<string, Setting>;
  capabilities: Record<string, boolean>;
  last_update: string | null;
  robot_name: string | null;
  model: string | null;
  connection_problem: string | null;
  demo: boolean;
}

export interface Session {
  id: number;
  started_at: string;
  ended_at: string | null;
  kind: "whole" | "rooms" | "zone";
  rooms: string[];
  started_by: "app" | "robot";
  result: string | null;
  area_m2: number | null;
  minutes: number | null;
}

export interface Status {
  robot: Robot;
  freshness: { stale: boolean; reason: string | null; age_seconds: number | null };
  current_session: Session | null;
  server_time: string;
  mode: "homeassistant" | "demo";
}

export type CommandStatus = "confirmed" | "sent" | "done" | "failed" | "rejected";

export interface CommandResult {
  status: CommandStatus;
  message: string;
  command: string;
}

export interface MapMeta {
  available: boolean;
  error: string | null;
  updated: string | null;
  active_map?: string | null;
  has_pixel_layer?: boolean;
  carpet_found?: boolean | null;
}

export interface AnnouncementSettings {
  enabled: boolean;
  tts_entity: string;
  media_player: string;
  language: string;
  volume: number | null;
  notify_service: string;
  events: Record<string, boolean>;
}

export interface SpeechTargets {
  tts_entities: string[];
  media_players: string[];
  notify_services: string[];
}

export interface LogEvent {
  id: number;
  ts: string;
  level: string;
  kind: string;
  message: string;
}

export interface CommandLog {
  id: number;
  ts: string;
  name: string;
  params: Record<string, unknown>;
  status: string;
  message: string;
}
