import {latLngToCell} from 'h3-js';
import type {Manifest, Position, RawRide, RideView, RouteEntry} from './types';

const base = `${import.meta.env.BASE_URL}data/`;

async function readJson<T>(file: string): Promise<T> {
  const response = await fetch(`${base}${file}`);
  if (!response.ok) throw new Error(`Could not load ${file}: HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

export function parsePosition(value: unknown): Position | null {
  if (typeof value !== 'string') return null;
  const values = value.split(',').map(Number);
  if (values.length < 2 || values.some((item) => !Number.isFinite(item))) return null;
  const [longitude, latitude] = values;
  if (Math.abs(longitude) > 180 || Math.abs(latitude) > 90) return null;
  return [longitude, latitude];
}

function number(value: unknown): number {
  const result = Number(value ?? 0);
  return Number.isFinite(result) ? result : 0;
}

function haversine(one: Position, two: Position): number {
  const radians = (value: number) => value * Math.PI / 180;
  const [lon1, lat1] = one;
  const [lon2, lat2] = two;
  const a = Math.sin(radians(lat2 - lat1) / 2) ** 2
    + Math.cos(radians(lat1)) * Math.cos(radians(lat2)) * Math.sin(radians(lon2 - lon1) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(a));
}

function pathLength(path: Position[]): number {
  return path.slice(1).reduce((total, point, index) => total + haversine(path[index], point), 0);
}

function cell(position: Position | null): string {
  return position ? latLngToCell(position[1], position[0], 9) : 'unknown';
}

export async function loadDataset(onProgress: (message: string) => void): Promise<{manifest: Manifest; rides: RideView[]}> {
  const manifest = await readJson<Manifest>('manifest.json');
  onProgress('Loading raw rides…');
  const rideSource = await readJson<{rides: RawRide[]}>(manifest.rideFile);
  const routes = new Map<string, RouteEntry>();
  for (const [index, descriptor] of manifest.routeFiles.entries()) {
    onProgress(`Loading route archive ${index + 1} of ${manifest.routeFiles.length}…`);
    const source = await readJson<{routes: Record<string, RouteEntry>}>(descriptor.file);
    Object.entries(source.routes).forEach(([id, entry]) => routes.set(id, entry));
  }
  onProgress('Building spatial index…');
  const prelim = rideSource.rides.flatMap((raw): RideView[] => {
    const start = new Date(String(raw.startTime ?? '').replace(' ', 'T'));
    if (Number.isNaN(start.getTime())) return [];
    const parsedEnd = new Date(String(raw.endTime ?? '').replace(' ', 'T'));
    const end = Number.isNaN(parsedEnd.getTime()) ? null : parsedEnd;
    const startPosition = parsePosition(raw.startGps);
    const endPosition = parsePosition(raw.endGps);
    const route = routes.get(String(raw.useId));
    const trace = route?.response?.locus?.map((point) => parsePosition(point.gpsAddress)).filter((point): point is Position => Boolean(point)) ?? [];
    const fallback = startPosition && endPosition ? [startPosition, endPosition] : [];
    const path = trace.length >= 2 ? trace : fallback;
    const duration = end ? Math.max(0, (end.getTime() - start.getTime()) / 60000) : 0;
    const originCell = cell(startPosition);
    const destinationCell = cell(endPosition);
    return [{
      id: String(raw.useId), raw, start, end, duration, billedMinutes: Math.max(1, Math.ceil(duration)),
      distanceKm: number(raw.useDist) > 0 ? number(raw.useDist) / 1000 : pathLength(path),
      paidNok: number(raw.paidNum) / 100, payableNok: number(raw.payableNum) / 100,
      startPosition, endPosition, path, hasTrace: trace.length >= 2,
      weekday: start.getDay(), hour: start.getHours(), month: start.toISOString().slice(0, 7),
      year: String(start.getFullYear()), originCell, destinationCell,
      corridor: [originCell, destinationCell].sort().join('↔'), commute: false,
    }];
  });
  const corridors = new Map<string, {count: number; directions: Set<string>}>();
  prelim.forEach((ride) => {
    const item = corridors.get(ride.corridor) ?? {count: 0, directions: new Set<string>()};
    item.count += 1;
    item.directions.add(`${ride.originCell}>${ride.destinationCell}`);
    corridors.set(ride.corridor, item);
  });
  prelim.forEach((ride) => {
    const corridor = corridors.get(ride.corridor);
    ride.commute = ride.weekday >= 1 && ride.weekday <= 5 && Boolean(corridor && corridor.count >= 10 && corridor.directions.size >= 2);
  });
  return {manifest, rides: prelim.sort((a, b) => a.start.getTime() - b.start.getTime())};
}

export const weekdayName = (day: number) => ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][day];
