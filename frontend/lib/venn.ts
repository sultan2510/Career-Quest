import { CIRCLES, type Circle } from '@/lib/ikigai';

export const ELLIPSES: Record<Circle, [number, number, number, number, number]> = {
  love: [.65, .47, .35, .20, 45], good: [.35, .47, .35, .20, 135],
  needs: [.50, .57, .33, .15, 45], paid: [.50, .57, .35, .15, 135],
};
export function inside(circle: Circle, x: number, y: number) {
  const [cx, cy, a, b, angle] = ELLIPSES[circle];
  const t = angle * Math.PI / 180, dx = x - cx, dy = y - cy;
  const u = dx * Math.cos(t) + dy * Math.sin(t);
  const v = -dx * Math.sin(t) + dy * Math.cos(t);
  return (u / a) ** 2 + (v / b) ** 2 <= 1;
}
export const membership = (x: number, y: number) => CIRCLES.filter(c => inside(c, x, y));
export const regionKey = (members: Circle[]) => members.join('|');

/** Sample interior positions and select only points with exactly the requested membership. */
export function regionPoints(grid = 130): Record<string, [number, number][]> {
  const out: Record<string, [number, number][]> = {};
  for (let iy = 0; iy < grid; iy++) for (let ix = 0; ix < grid; ix++) {
    const p: [number, number] = [(ix + .5) / grid, (iy + .5) / grid];
    const key = regionKey(membership(...p));
    if (key) (out[key] ??= []).push(p);
  }
  return out;
}

export function placeInRegions(items: { id: string; members: Circle[] }[]) {
  const points = regionPoints();
  const result: Record<string, [number, number]> = {};
  const groups: Record<string, string[]> = {};
  for (const item of items) if (item.members.length) (groups[regionKey(item.members)] ??= []).push(item.id);
  for (const [key, ids] of Object.entries(groups)) {
    const pool = points[key] ?? [];
    const step = Math.max(1, Math.floor(pool.length / 250));
    const candidates = pool.filter((_, i) => i % step === 0);
    const placed: [number, number][] = [];
    for (const id of ids) {
      if (!candidates.length) continue;
      const best = candidates.reduce((best, p) => {
        const spread = (q: [number, number]) => placed.length ? Math.min(...placed.map(z => (q[0] - z[0]) ** 2 + (q[1] - z[1]) ** 2)) : (q[0] - .5) ** 2 + (q[1] - .5) ** 2;
        return spread(p) > spread(best) ? p : best;
      }, candidates[0]);
      result[id] = best;
      placed.push(best);
    }
  }
  return result;
}
