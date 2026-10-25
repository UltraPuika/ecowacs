import type { Robot, Status } from "../types";

export function robot(overrides: Partial<Robot> = {}): Robot {
  return {
    backend_connected: true,
    robot_available: true,
    activity: "docked",
    battery: 76,
    fan_speed: "normal",
    fan_speed_options: ["quiet", "normal", "max", "max_plus"],
    work_mode: "vacuum",
    work_mode_options: ["vacuum", "vacuum_and_mop", "mop_after_vacuum"],
    rooms: [
      { id: "1", name: "Virtuve" },
      { id: "2", name: "Gaitenis" },
    ],
    active_map: "Stāvs 1",
    map_options: ["Stāvs 1"],
    map_updated: new Date().toISOString(),
    error: null,
    station_state: "idle",
    last_clean_area: 20,
    last_clean_minutes: 35,
    settings: {},
    capabilities: {
      start: true, pause: true, stop: true, return_to_base: true, locate: true,
      clean_rooms: true, clean_zone: true, work_mode: true, map: true, fan_speed: true,
    },
    last_update: new Date().toISOString(),
    robot_name: "Robis",
    model: "DEEBOT X9 PRO OMNI",
    connection_problem: null,
    demo: false,
    ...overrides,
  };
}

export function status(r: Partial<Robot> = {}, extra: Partial<Status> = {}): Status {
  return {
    robot: robot(r),
    freshness: { stale: false, reason: null, age_seconds: 1 },
    current_session: null,
    server_time: new Date().toISOString(),
    mode: "homeassistant",
    ...extra,
  };
}
