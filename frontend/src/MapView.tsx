import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { api, ApiError } from "./api";
import { centroid, dragZone, pointInPolygon, robotToSvg, zoneSizeMetres, type Pt, type Rect } from "./mapGeometry";
import type { MapMeta, Room } from "./types";

/** Loads /api/map/meta again whenever the robot reports a new map. */
export function useMapMeta(mapUpdated: string | null) {
  const [meta, setMeta] = useState<MapMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    try {
      setMeta(await api.get<MapMeta>("/api/map/meta"));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Neizdevās ielādēt karti.");
    }
  }, []);
  useEffect(() => {
    void reload();
  }, [reload, mapUpdated]);
  return { meta, error, reload };
}

export function mapImageUrl(mapUpdated: string | null, showCarpets = true, version = 0): string {
  return `/api/map.svg?carpets=${showCarpets ? "show" : "hide"}&v=${version}-${encodeURIComponent(mapUpdated ?? "")}`;
}

const CARPET_KEY = "deebot.showCarpets";

export function loadShowCarpets(): boolean {
  try {
    return window.localStorage.getItem(CARPET_KEY) !== "0";
  } catch {
    return true;
  }
}

export function saveShowCarpets(value: boolean): void {
  try {
    window.localStorage.setItem(CARPET_KEY, value ? "1" : "0");
  } catch {
    /* storage unavailable: preference lasts for this visit only */
  }
}

const ROOM_COLORS = ["#7fb4ff", "#ffbf7a", "#8edcaa", "#c9a6ff", "#ffd966", "#f5a3c0", "#8fdbe8", "#c5d97a"];
const MAX_ZOOM = 10;
const TAP_SLOP = 6;

type Gesture =
  | { kind: "pan"; view: Rect; x: number; y: number; moved: boolean }
  | { kind: "pinch"; view: Rect; dist: number; anchor: Pt }
  | { kind: "zone"; handle: string; zone: Rect; x: number; y: number };

interface Props {
  src: string;
  viewBox: [number, number, number, number];
  /** Map rotation; null when robot coordinates are unknown (no room shapes, no zones). */
  rotation: number | null;
  label: string;
  rooms?: Room[];
  selectedRooms?: string[];
  onToggleRoom?: (id: string) => void;
  zone?: Rect | null;
  onZoneChange?: (zone: Rect) => void;
  onImageError?: () => void;
}

/** Pan with one finger, pinch or scroll to zoom, tap rooms, drag and resize a zone. */
export function MapView({
  src,
  viewBox,
  rotation,
  label,
  rooms = [],
  selectedRooms = [],
  onToggleRoom,
  zone = null,
  onZoneChange,
  onImageError,
}: Props) {
  const [bx, by, bw, bh] = viewBox;
  const base = useMemo<Rect>(() => ({ x: bx, y: by, w: bw, h: bh }), [bx, by, bw, bh]);
  const [view, setViewState] = useState<Rect>(base);
  const viewRef = useRef(base);
  const setView = useCallback((v: Rect) => {
    viewRef.current = v;
    setViewState(v);
  }, []);
  useEffect(() => setView(base), [base, setView]);

  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [size, setSize] = useState({ w: 360, h: 300 });
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setSize({ w: width, h: height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const bounds = () => {
    const r = svgRef.current?.getBoundingClientRect();
    return r && r.width > 0 && r.height > 0 ? r : { left: 0, top: 0, width: size.w, height: size.h };
  };
  const unitsPerPx = (v: Rect, r: { width: number; height: number }) => Math.max(v.w / r.width, v.h / r.height);

  const clientToSvg = (cx: number, cy: number, v: Rect): Pt => {
    const r = bounds();
    const s = unitsPerPx(v, r);
    return [v.x + (cx - r.left - (r.width - v.w / s) / 2) * s, v.y + (cy - r.top - (r.height - v.h / s) / 2) * s];
  };

  /** Keep the centre of the view on the map so it cannot be lost off-screen. */
  const clampView = (v: Rect): Rect => {
    const cx = Math.min(Math.max(v.x + v.w / 2, base.x), base.x + base.w);
    const cy = Math.min(Math.max(v.y + v.h / 2, base.y), base.y + base.h);
    return { ...v, x: cx - v.w / 2, y: cy - v.h / 2 };
  };

  /** View of width w where the SVG point `anchor` sits under the screen point `client`. */
  const zoomAt = (anchor: Pt, client: { x: number; y: number }, w: number): Rect => {
    const nw = Math.min(Math.max(w, base.w / MAX_ZOOM), base.w * 1.5);
    const nh = (nw * base.h) / base.w;
    const r = bounds();
    const s = unitsPerPx({ x: 0, y: 0, w: nw, h: nh }, r);
    return clampView({
      x: anchor[0] - (client.x - r.left - (r.width - nw / s) / 2) * s,
      y: anchor[1] - (client.y - r.top - (r.height - nh / s) / 2) * s,
      w: nw,
      h: nh,
    });
  };

  const zoomBy = (factor: number) => {
    const r = bounds();
    const centre = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    const v = viewRef.current;
    setView(zoomAt(clientToSvg(centre.x, centre.y, v), centre, v.w / factor));
  };

  const shapes = useMemo(() => {
    if (rotation === null) return [];
    return rooms.flatMap((room, i) => {
      if (!room.outline || room.outline.length < 3) return [];
      const pts = room.outline.map((p) => robotToSvg(p, rotation));
      return [{ room, pts, center: centroid(pts), color: ROOM_COLORS[i % ROOM_COLORS.length] }];
    });
  }, [rooms, rotation]);

  // --- pointer gestures -------------------------------------------------------------
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<Gesture | null>(null);

  const twoPointers = () => {
    const [a, b] = [...pointers.current.values()];
    return { mid: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, dist: Math.hypot(a.x - b.x, a.y - b.y) || 1 };
  };

  const onPointerDown = (e: ReactPointerEvent<SVGSVGElement>) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    svgRef.current?.setPointerCapture?.(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2) {
      const { mid, dist } = twoPointers();
      gesture.current = { kind: "pinch", view: viewRef.current, dist, anchor: clientToSvg(mid.x, mid.y, viewRef.current) };
      return;
    }
    if (pointers.current.size > 2) return;
    const handle = (e.target as Element).closest?.("[data-zone]")?.getAttribute("data-zone");
    if (handle && zone && onZoneChange) {
      gesture.current = { kind: "zone", handle, zone, x: e.clientX, y: e.clientY };
    } else {
      gesture.current = { kind: "pan", view: viewRef.current, x: e.clientX, y: e.clientY, moved: false };
    }
  };

  const onPointerMove = (e: ReactPointerEvent<SVGSVGElement>) => {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const g = gesture.current;
    if (!g) return;
    if (g.kind === "pinch") {
      if (pointers.current.size < 2) return;
      const { mid, dist } = twoPointers();
      setView(zoomAt(g.anchor, mid, (g.view.w * g.dist) / dist));
    } else if (g.kind === "pan") {
      const dx = e.clientX - g.x;
      const dy = e.clientY - g.y;
      if (!g.moved && Math.hypot(dx, dy) < TAP_SLOP) return;
      g.moved = true;
      const s = unitsPerPx(g.view, bounds());
      setView(clampView({ ...g.view, x: g.view.x - dx * s, y: g.view.y - dy * s }));
    } else {
      const s = unitsPerPx(viewRef.current, bounds());
      onZoneChange?.(dragZone(g.zone, g.handle, (e.clientX - g.x) * s, (e.clientY - g.y) * s));
    }
  };

  const onPointerEnd = (e: ReactPointerEvent<SVGSVGElement>) => {
    if (!pointers.current.delete(e.pointerId)) return;
    const g = gesture.current;
    if (e.type === "pointerup" && g?.kind === "pan" && !g.moved && onToggleRoom) {
      const p = clientToSvg(e.clientX, e.clientY, viewRef.current);
      const hit = shapes.find((s) => pointInPolygon(p, s.pts));
      if (hit) onToggleRoom(hit.room.id);
    }
    if (pointers.current.size === 1) {
      const [p] = [...pointers.current.values()];
      gesture.current = { kind: "pan", view: viewRef.current, x: p.x, y: p.y, moved: true };
    } else if (pointers.current.size === 0) {
      gesture.current = null;
    }
  };

  // React registers wheel listeners as passive, so preventDefault needs a native listener.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const v = viewRef.current;
      const client = { x: e.clientX, y: e.clientY };
      setView(zoomAt(clientToSvg(client.x, client.y, v), client, v.w * Math.exp(e.deltaY * 0.0015)));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  const k = unitsPerPx(view, { width: size.w, height: size.h });
  const zoneSize = zone ? zoneSizeMetres(zone) : null;
  const corners: [string, number, number][] = zone
    ? [
        ["nw", zone.x, zone.y],
        ["ne", zone.x + zone.w, zone.y],
        ["sw", zone.x, zone.y + zone.h],
        ["se", zone.x + zone.w, zone.y + zone.h],
      ]
    : [];

  return (
    <div className="mapview" ref={wrapRef}>
      <svg
        ref={svgRef}
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        role="group"
        aria-label={label}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
      >
        <image href={src} x={bx} y={by} width={bw} height={bh} onError={onImageError} />
        {shapes.map(({ room, pts, color }) => (
          <polygon
            key={room.id}
            className={`map-room ${selectedRooms.includes(room.id) ? "selected" : ""}`}
            points={pts.map((p) => p.join(",")).join(" ")}
            style={selectedRooms.includes(room.id) ? undefined : { fill: color }}
          />
        ))}
        {shapes.map(({ room, center }) => {
          const order = selectedRooms.indexOf(room.id) + 1;
          return (
            <g key={room.id} className="map-room-label" transform={`translate(${center[0]} ${center[1]})`}>
              {order > 0 && (
                <>
                  <circle cy={-20 * k} r={10 * k} className="map-room-badge" />
                  <text y={-20 * k} dy="0.35em" fontSize={12 * k} className="map-room-badge-text">
                    {order}
                  </text>
                </>
              )}
              <text dy="0.35em" fontSize={13 * k} strokeWidth={3 * k}>
                {room.name}
              </text>
            </g>
          );
        })}
        {zone && (
          <g className={`map-zone ${onZoneChange ? "editable" : ""}`}>
            <rect data-zone="move" x={zone.x} y={zone.y} width={zone.w} height={zone.h} />
            {zoneSize && (
              <text x={zone.x + zone.w / 2} y={zone.y - 8 * k} fontSize={12 * k} strokeWidth={3 * k}>
                {zoneSize[0].toFixed(1)} × {zoneSize[1].toFixed(1)} m
              </text>
            )}
            {onZoneChange &&
              corners.map(([handle, cx, cy]) => (
                <g key={handle} data-zone={handle} className="map-zone-handle">
                  <circle cx={cx} cy={cy} r={22 * k} fill="transparent" />
                  <circle cx={cx} cy={cy} r={9 * k} className="map-zone-dot" />
                </g>
              ))}
          </g>
        )}
      </svg>
      <div className="map-controls">
        <button type="button" aria-label="Tuvināt" onClick={() => zoomBy(1.5)}>
          +
        </button>
        <button type="button" aria-label="Tālināt" onClick={() => zoomBy(1 / 1.5)}>
          −
        </button>
        <button type="button" aria-label="Rādīt visu karti" onClick={() => setView(base)}>
          ⤢
        </button>
      </div>
    </div>
  );
}
