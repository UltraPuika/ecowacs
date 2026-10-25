import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { Status } from "./types";

export type LinkState = "connecting" | "live" | "offline";

/** Live robot status: WebSocket push, with HTTP polling as a fallback. */
export function useRobot(enabled: boolean) {
  const [status, setStatus] = useState<Status | null>(null);
  const [link, setLink] = useState<LinkState>("connecting");
  const [receivedAt, setReceivedAt] = useState<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const accept = useCallback((data: Status) => {
    setStatus(data);
    setReceivedAt(Date.now());
  }, []);

  const refresh = useCallback(async () => {
    try {
      accept(await api.get<Status>("/api/status"));
      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return false;
      setLink("offline");
      return false;
    }
  }, [accept]);

  useEffect(() => {
    if (!enabled) return;
    let closed = false;
    let retry: number | undefined;
    let poll: number | undefined;
    let delay = 1000;

    const connect = () => {
      if (closed) return;
      setLink((prev) => (prev === "live" ? prev : "connecting"));
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${window.location.host}/api/ws`);
      wsRef.current = ws;
      ws.onopen = () => {
        delay = 1000;
        setLink("live");
      };
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "status") accept(msg.data as Status);
        } catch {
          /* ignore malformed message */
        }
      };
      ws.onclose = () => {
        if (closed) return;
        setLink("offline");
        void refresh();
        retry = window.setTimeout(connect, delay);
        delay = Math.min(delay * 2, 30000);
      };
    };

    void refresh();
    connect();
    // Fallback polling keeps the screen honest even if the socket silently stalls.
    poll = window.setInterval(() => {
      if (wsRef.current?.readyState !== WebSocket.OPEN) void refresh();
    }, 15000);

    const onVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      closed = true;
      window.clearTimeout(retry);
      window.clearInterval(poll);
      document.removeEventListener("visibilitychange", onVisible);
      wsRef.current?.close();
    };
  }, [enabled, refresh, accept]);

  return { status, link, receivedAt, refresh };
}
