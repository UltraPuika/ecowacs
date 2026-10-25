import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Home } from "../pages/Home";
import { status } from "./fixtures";

function mockFetch(result: unknown, delay = 0) {
  const fn = vi.fn(
    () =>
      new Promise<Response>((resolve) =>
        setTimeout(() => resolve(new Response(JSON.stringify(result), { status: 200 })), delay),
      ),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("Home screen (Latvian)", () => {
  it("shows docked state, battery and main action in Latvian", () => {
    render(<Home status={status()} onChooseRooms={() => {}} />);
    expect(screen.getByTestId("activity")).toHaveTextContent("Robots uzlādējas");
    expect(screen.getByText("76%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sākt tīrīšanu/ })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Atgriezties uz staciju/ })).toBeNull();
    expect(screen.getByText(/Pēdējā ziņa no robota/)).toBeInTheDocument();
  });

  it("shows pause and stop while cleaning, with room names", () => {
    const s = status({ activity: "cleaning" }, {
      current_session: {
        id: 1, started_at: "", ended_at: null, kind: "rooms", rooms: ["Virtuve", "Gaitenis"],
        started_by: "app", result: null, area_m2: null, minutes: null,
      },
    });
    render(<Home status={s} onChooseRooms={() => {}} />);
    expect(screen.getByTestId("activity")).toHaveTextContent("Tīra: Virtuve un Gaitenis");
    expect(screen.getByRole("button", { name: /Pauzēt/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Apturēt/ })).toBeInTheDocument();
  });

  it("shows resume when paused", () => {
    render(<Home status={status({ activity: "paused" })} onChooseRooms={() => {}} />);
    expect(screen.getByTestId("activity")).toHaveTextContent("Tīrīšana nopauzēta");
    expect(screen.getByRole("button", { name: /Turpināt/ })).toBeInTheDocument();
  });

  it("shows a Latvian error with a next step", () => {
    const s = status({
      activity: "error",
      error: { code: 105, title: "Robots ir iestrēdzis", explanation: "x", action: "Atrodiet robotu.", original: null },
    });
    render(<Home status={s} onChooseRooms={() => {}} />);
    expect(screen.getByRole("heading", { name: "Robots ir iestrēdzis" })).toBeInTheDocument();
    expect(screen.getByText("Ko darīt:")).toBeInTheDocument();
  });

  it("says there is no connection instead of showing a stale state", () => {
    render(<Home status={status({ robot_available: false })} onChooseRooms={() => {}} />);
    expect(screen.getByTestId("activity")).toHaveTextContent("Nav savienojuma ar robotu");
  });

  it("asks for confirmation before stopping", async () => {
    const fetchMock = mockFetch({ status: "confirmed", message: "Tīrīšana ir apturēta.", command: "stop" });
    render(<Home status={status({ activity: "cleaning" })} onChooseRooms={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /Apturēt/ }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Apturēt tīrīšanu?");
    expect(fetchMock).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Atcelt" }));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends a command only once on a double tap and shows the honest result", async () => {
    const fetchMock = mockFetch(
      { status: "sent", message: "Komanda nosūtīta, bet robots vēl nav apstiprinājis.", command: "start" },
      50,
    );
    render(<Home status={status()} onChooseRooms={() => {}} />);
    const button = screen.getByRole("button", { name: /Sākt tīrīšanu/ });
    await userEvent.dblClick(button);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("nav apstiprinājis"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-Requested-With"]).toBe("deebot-lv");
  });

  it("hides unsupported buttons", () => {
    const s = status();
    s.robot.capabilities = { ...s.robot.capabilities, clean_rooms: false, locate: false };
    render(<Home status={s} onChooseRooms={() => {}} />);
    expect(screen.queryByRole("button", { name: /Tīrīt tikai dažas telpas/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Kur ir robots/ })).toBeNull();
  });
});
