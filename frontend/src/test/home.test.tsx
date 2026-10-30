import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { dragZone, robotToSvg, svgToRobot, zoneToRobot } from "../mapGeometry";
import { Home } from "../pages/Home";
import { status } from "./fixtures";

function mockFetch(result: unknown, delay = 0) {
  const fn = vi.fn(
    (url: RequestInfo | URL) =>
      new Promise<Response>((resolve) => {
        const body = String(url).startsWith("/api/map/meta") ? { available: false, error: null, updated: null } : result;
        setTimeout(() => resolve(new Response(JSON.stringify(body), { status: 200 })), delay);
      }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

const commandCalls = (fn: ReturnType<typeof mockFetch>) =>
  fn.mock.calls.filter(([u]) => String(u) === "/api/commands") as unknown as [string, RequestInit][];

afterEach(() => vi.unstubAllGlobals());

describe("Home screen (Latvian)", () => {
  it("shows docked state, battery and main action in Latvian", () => {
    mockFetch({});
    render(<Home status={status()} />);
    expect(screen.getByTestId("activity")).toHaveTextContent("Robots uzlādējas");
    expect(screen.getByText("76%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sākt tīrīšanu/ })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Atgriezties uz staciju/ })).toBeNull();
    expect(screen.getByText(/Pēdējā ziņa no robota/)).toBeInTheDocument();
  });

  it("shows pause and stop while cleaning, with room names", () => {
    mockFetch({});
    const s = status({ activity: "cleaning" }, {
      current_session: {
        id: 1, started_at: "", ended_at: null, kind: "rooms", rooms: ["Virtuve", "Gaitenis"],
        started_by: "app", result: null, area_m2: null, minutes: null,
      },
    });
    render(<Home status={s} />);
    expect(screen.getByTestId("activity")).toHaveTextContent("Tīra: Virtuve un Gaitenis");
    expect(screen.getByRole("button", { name: /Pauzēt/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Apturēt/ })).toBeInTheDocument();
  });

  it("shows resume when paused", () => {
    mockFetch({});
    render(<Home status={status({ activity: "paused" })} />);
    expect(screen.getByTestId("activity")).toHaveTextContent("Tīrīšana nopauzēta");
    expect(screen.getByRole("button", { name: /Turpināt/ })).toBeInTheDocument();
  });

  it("shows a Latvian error with a next step", () => {
    mockFetch({});
    const s = status({
      activity: "error",
      error: { code: 105, title: "Robots ir iestrēdzis", explanation: "x", action: "Atrodiet robotu.", original: null },
    });
    render(<Home status={s} />);
    expect(screen.getByRole("heading", { name: "Robots ir iestrēdzis" })).toBeInTheDocument();
    expect(screen.getByText("Ko darīt:")).toBeInTheDocument();
  });

  it("says there is no connection instead of showing a stale state", () => {
    mockFetch({});
    render(<Home status={status({ robot_available: false })} />);
    expect(screen.getByTestId("activity")).toHaveTextContent("Nav savienojuma ar robotu");
  });

  it("asks for confirmation before stopping", async () => {
    const fetchMock = mockFetch({ status: "confirmed", message: "Tīrīšana ir apturēta.", command: "stop" });
    render(<Home status={status({ activity: "cleaning" })} />);
    await userEvent.click(screen.getByRole("button", { name: /Apturēt/ }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Apturēt tīrīšanu?");
    expect(commandCalls(fetchMock)).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Atcelt" }));
    expect(commandCalls(fetchMock)).toHaveLength(0);
  });

  it("sends a command only once on a double tap and shows the honest result", async () => {
    const fetchMock = mockFetch(
      { status: "sent", message: "Komanda nosūtīta, bet robots vēl nav apstiprinājis.", command: "start" },
      50,
    );
    render(<Home status={status()} />);
    const button = screen.getByRole("button", { name: /Sākt tīrīšanu/ });
    await userEvent.dblClick(button);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("nav apstiprinājis"));
    const calls = commandCalls(fetchMock);
    expect(calls).toHaveLength(1);
    expect((calls[0][1].headers as Record<string, string>)["X-Requested-With"]).toBe("deebot-lv");
  });

  it("hides unsupported buttons", () => {
    mockFetch({});
    const s = status();
    s.robot.capabilities = { ...s.robot.capabilities, clean_rooms: false, locate: false };
    render(<Home status={s} />);
    expect(screen.queryByRole("tab", { name: /Telpas/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Kur ir robots/ })).toBeNull();
  });

  it("cleans only the selected rooms", async () => {
    const fetchMock = mockFetch({
      status: "confirmed", message: "Robots sāka tīrīt izvēlētās telpas.", command: "clean_rooms",
    });
    render(<Home status={status()} />);
    await userEvent.click(screen.getByRole("tab", { name: /Telpas/ }));
    expect(screen.getByRole("button", { name: "Tīrīt izvēlētās telpas (0)" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /Gaitenis/ }));
    await userEvent.click(screen.getByRole("button", { name: "Tīrīt izvēlētās telpas (1)" }));
    await waitFor(() => expect(screen.getByText("Robots sāka tīrīt izvēlētās telpas.")).toBeInTheDocument());
    const [call] = commandCalls(fetchMock);
    expect(JSON.parse(String(call[1].body))).toEqual({ name: "clean_rooms", params: { rooms: ["2"], cleanings: 1 } });
  });
});

describe("map geometry", () => {
  it("matches deebot-client's SVG coordinates for every rotation", () => {
    // Verified against deebot-client: wall (1000,2000)-(3000,2000) is drawn at (20,-40)-(60,-40),
    // and at (40,20)-(40,60) when the map is rotated by 90°.
    expect(robotToSvg([1000, 2000], 0)).toEqual([20, -40]);
    expect(robotToSvg([3000, 2000], 90)).toEqual([40, 60]);
    for (const rot of [0, 90, 180, 270]) {
      const [x, y] = svgToRobot(robotToSvg([1234, -567], rot), rot);
      expect(x).toBeCloseTo(1234);
      expect(y).toBeCloseTo(-567);
    }
  });

  it("turns a drawn zone into ordered robot coordinates", () => {
    expect(zoneToRobot({ x: 20, y: -40, w: 40, h: 10 }, 0)).toEqual([1000, 1500, 3000, 2000]);
  });

  it("never lets a zone collapse when resizing", () => {
    const z = dragZone({ x: 0, y: 0, w: 20, h: 20 }, "se", -100, -100);
    expect(z.w).toBeGreaterThan(0);
    expect(z.h).toBeGreaterThan(0);
  });
});
