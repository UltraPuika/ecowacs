import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { MapPage } from "../pages/MapPage";
import { status } from "./fixtures";

class FakeSocket {
  static OPEN = 1;
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  close() {}
}

function routeFetch(routes: Record<string, unknown>) {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    if (!key) return new Response("{}", { status: 404 });
    const value = routes[key];
    if (value instanceof Response) return value;
    return new Response(JSON.stringify(value), { status: 200 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => vi.stubGlobal("WebSocket", FakeSocket));
afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("shows the Latvian login screen when not logged in", async () => {
    routeFetch({ "/api/session": { authenticated: false, auth_required: true } });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Ieiet" })).toBeInTheDocument();
    expect(screen.getByLabelText("Parole")).toBeInTheDocument();
  });

  it("shows the demo banner so simulated data is never mistaken for real", async () => {
    routeFetch({
      "/api/session": { authenticated: true, auth_required: true },
      "/api/status": status({ demo: true }, { mode: "demo" }),
    });
    render(<App />);
    expect(await screen.findByText(/DEMO REŽĪMS/)).toBeInTheDocument();
  });

  it("warns when data is stale", async () => {
    routeFetch({
      "/api/session": { authenticated: true, auth_required: true },
      "/api/status": status({}, {
        freshness: { stale: true, reason: "Robots ilgi nav sūtījis jaunus datus.", age_seconds: 5000 },
      }),
    });
    render(<App />);
    expect(await screen.findByTestId("stale-banner")).toHaveTextContent("Dati var būt novecojuši");
  });

  it("has the four Latvian navigation tabs", async () => {
    routeFetch({
      "/api/session": { authenticated: true, auth_required: true },
      "/api/status": status(),
      "/api/history": { sessions: [] },
    });
    render(<App />);
    for (const name of ["Sākums", "Karte", "Tīrīšanas vēsture", "Iestatījumi"]) {
      expect(await screen.findByRole("button", { name: new RegExp(name) })).toBeInTheDocument();
    }
    await userEvent.click(screen.getByRole("button", { name: /Tīrīšanas vēsture/ }));
    expect(await screen.findByText("Vēl nav nevienas tīrīšanas.")).toBeInTheDocument();
  });
});

describe("Map page", () => {
  it("explains that hiding carpets only changes this app's picture", async () => {
    routeFetch({
      "/api/map/meta": { available: true, error: null, updated: null, has_pixel_layer: true, carpet_found: true },
    });
    render(<MapPage status={status()} />);
    expect(await screen.findByText("Paklāji šajā kartē ir atrasti.")).toBeInTheDocument();
    expect(screen.getByText(/Robots joprojām atpazīst paklājus/)).toBeInTheDocument();
    const toggle = screen.getByRole("switch", { name: /Rādīt paklājus kartē/ });
    await userEvent.click(toggle);
    expect(screen.getByRole("switch", { name: /Slēpt paklājus kartē/ })).not.toBeChecked();
    expect(screen.getByRole("img").getAttribute("src")).toContain("carpets=hide");
  });

  it("says honestly when the map has no carpet layer", async () => {
    routeFetch({
      "/api/map/meta": { available: true, error: null, updated: null, has_pixel_layer: false, carpet_found: null },
    });
    render(<MapPage status={status()} />);
    expect(await screen.findByText(/paklāju slānis nav pieejams/)).toBeInTheDocument();
  });

  it("cleans only the selected rooms", async () => {
    const fetchMock = routeFetch({
      "/api/map/meta": { available: false, error: null, updated: null },
      "/api/commands": { status: "confirmed", message: "Robots sāka tīrīt izvēlētās telpas.", command: "clean_rooms" },
    });
    render(<MapPage status={status()} />);
    const button = screen.getByRole("button", { name: "Tīrīt izvēlētās telpas (0)" });
    expect(button).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Gaitenis" }));
    await userEvent.click(screen.getByRole("button", { name: "Tīrīt izvēlētās telpas (1)" }));
    await waitFor(() => expect(screen.getByText("Robots sāka tīrīt izvēlētās telpas.")).toBeInTheDocument());
    const call = fetchMock.mock.calls.find(([u]) => String(u) === "/api/commands") as unknown as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toEqual({ name: "clean_rooms", params: { rooms: ["2"], cleanings: 1 } });
  });
});
