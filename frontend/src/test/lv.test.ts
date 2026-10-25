import { describe, expect, it } from "vitest";
import { activityText, ACTIVITY, joinLv, RESULT, SETTING, T, timeAgo, WORK_MODE } from "../lv";
import { robot } from "./fixtures";

describe("Latvian texts", () => {
  it("uses the agreed labels", () => {
    expect(T.start).toBe("Sākt tīrīšanu");
    expect(T.pause).toBe("Pauzēt");
    expect(T.resume).toBe("Turpināt");
    expect(T.stop).toBe("Apturēt");
    expect(T.returnHome).toBe("Atgriezties uz staciju");
    expect(T.noConnectionRobot).toBe("Nav savienojuma ar robotu");
    expect(T.needsAttention).toBe("Nepieciešama uzmanība");
    expect(T.nav).toEqual({ home: "Sākums", map: "Karte", history: "Tīrīšanas vēsture", settings: "Iestatījumi" });
  });

  it("has no English leftovers in user-facing tables", () => {
    const english = /\b(the|robot is|cleaning|error|settings|start|stop)\b/i;
    for (const table of [ACTIVITY, WORK_MODE, RESULT]) {
      for (const text of Object.values(table)) expect(text).not.toMatch(english);
    }
    for (const { label, help } of Object.values(SETTING)) {
      expect(label).not.toMatch(english);
      if (help) expect(help).not.toMatch(english);
    }
  });

  it("formats relative time with correct Latvian forms", () => {
    const now = new Date("2026-10-25T12:00:00Z");
    const ago = (s: number) => timeAgo(new Date(now.getTime() - s * 1000).toISOString(), now);
    expect(ago(10)).toBe("tikko");
    expect(ago(60)).toBe("pirms 1 minūtes");
    expect(ago(5 * 60)).toBe("pirms 5 minūtēm");
    expect(ago(21 * 60)).toBe("pirms 21 minūtes");
    expect(ago(11 * 60)).toBe("pirms 11 minūtēm");
    expect(ago(3600)).toBe("pirms 1 stundas");
    expect(ago(3 * 86400)).toBe("pirms 3 dienām");
    expect(timeAgo(null)).toBe("nav zināms");
  });

  it("joins names the Latvian way", () => {
    expect(joinLv(["Virtuve", "Gaitenis", "Vannas istaba"])).toBe("Virtuve, Gaitenis un Vannas istaba");
  });

  it("describes charging versus fully charged", () => {
    expect(activityText(robot({ battery: 100 }))).toBe("Robots ir uzlādēts un gatavs");
    expect(activityText(robot({ battery: 40 }))).toBe("Robots uzlādējas");
    expect(activityText(robot({ backend_connected: false }))).toBe("Nav savienojuma ar robotu");
  });
});
