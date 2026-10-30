import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Settings } from "../pages/Settings";
import { status } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

function stubFetch() {
  const fn = vi.fn(async () => new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("Settings without Home Assistant", () => {
  it("explains that announcements are unavailable instead of offering dead controls", () => {
    const fetchMock = stubFetch();
    const s = status({}, { mode: "direct" });
    s.robot.capabilities = { ...s.robot.capabilities, announcements: false };
    render(<Settings status={s} onLogout={() => {}} authRequired />);
    expect(screen.getByTestId("no-announcements")).toHaveTextContent("bez Home Assistant");
    expect(screen.queryByText("Ieslēgt paziņojumus latviski")).toBeNull();
    // the announcement form must not even try to load Home Assistant speakers
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("still offers announcements when Home Assistant is connected", () => {
    stubFetch();
    const s = status({}, { mode: "homeassistant" });
    s.robot.capabilities = { ...s.robot.capabilities, announcements: true };
    render(<Settings status={s} onLogout={() => {}} authRequired />);
    expect(screen.queryByTestId("no-announcements")).toBeNull();
  });
});
