/**
 * Conversion between robot map coordinates (mm) and the SVG drawn by deebot-client.
 * deebot-client draws 1 SVG unit = 50 mm with the y axis flipped, then rotates the
 * whole map clockwise by the map's rotation angle.
 */
export type Pt = [number, number];

/** Axis-aligned rectangle in SVG units. */
export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

const MM_PER_UNIT = 50;

export function robotToSvg([x, y]: Pt, rotation: number): Pt {
  const a = x / MM_PER_UNIT;
  const b = -y / MM_PER_UNIT;
  switch (rotation) {
    case 90:
      return [-b, a];
    case 180:
      return [-a, -b];
    case 270:
      return [b, -a];
    default:
      return [a, b];
  }
}

export function svgToRobot([sx, sy]: Pt, rotation: number): Pt {
  let a = sx;
  let b = sy;
  if (rotation === 90) [a, b] = [sy, -sx];
  else if (rotation === 180) [a, b] = [-sx, -sy];
  else if (rotation === 270) [a, b] = [-sy, sx];
  return [a * MM_PER_UNIT, -b * MM_PER_UNIT];
}

/** Zone rectangle → [x1, y1, x2, y2] robot coordinates with x1 < x2 and y1 < y2. */
export function zoneToRobot(zone: Rect, rotation: number): [number, number, number, number] {
  const [ax, ay] = svgToRobot([zone.x, zone.y], rotation);
  const [bx, by] = svgToRobot([zone.x + zone.w, zone.y + zone.h], rotation);
  return [
    Math.round(Math.min(ax, bx)),
    Math.round(Math.min(ay, by)),
    Math.round(Math.max(ax, bx)),
    Math.round(Math.max(ay, by)),
  ];
}

/** Zone size in metres (width × height as seen on screen). */
export function zoneSizeMetres(zone: Rect): [number, number] {
  return [(zone.w * MM_PER_UNIT) / 1000, (zone.h * MM_PER_UNIT) / 1000];
}

export function pointInPolygon([x, y]: Pt, poly: Pt[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** Smallest zone side: 0.5 m. */
export const MIN_ZONE = 10;

/** Move ("move") or resize (corner "nw" | "ne" | "sw" | "se") a zone by dx, dy SVG units. */
export function dragZone(zone: Rect, handle: string, dx: number, dy: number): Rect {
  if (handle === "move") return { ...zone, x: zone.x + dx, y: zone.y + dy };
  let x1 = zone.x;
  let y1 = zone.y;
  let x2 = zone.x + zone.w;
  let y2 = zone.y + zone.h;
  if (handle.includes("w")) x1 = Math.min(x1 + dx, x2 - MIN_ZONE);
  if (handle.includes("e")) x2 = Math.max(x2 + dx, x1 + MIN_ZONE);
  if (handle.includes("n")) y1 = Math.min(y1 + dy, y2 - MIN_ZONE);
  if (handle.includes("s")) y2 = Math.max(y2 + dy, y1 + MIN_ZONE);
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

/** Area centroid of a simple polygon (falls back to the vertex average). */
export function centroid(poly: Pt[]): Pt {
  let area = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const cross = poly[j][0] * poly[i][1] - poly[i][0] * poly[j][1];
    area += cross;
    cx += (poly[j][0] + poly[i][0]) * cross;
    cy += (poly[j][1] + poly[i][1]) * cross;
  }
  if (Math.abs(area) < 1e-9) {
    const n = poly.length || 1;
    return [poly.reduce((s, p) => s + p[0], 0) / n, poly.reduce((s, p) => s + p[1], 0) / n];
  }
  return [cx / (3 * area), cy / (3 * area)];
}
