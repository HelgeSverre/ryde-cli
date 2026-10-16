export type Position = [number, number];

export interface RawRide {
  useId: number | string;
  startTime?: string;
  endTime?: string;
  startGps?: string;
  endGps?: string;
  startAdd?: string;
  endAdd?: string;
  useDist?: number | string;
  paidNum?: number | string;
  payableNum?: number | string;
  monType?: string;
  [key: string]: unknown;
}

export interface RouteEntry {
  useId: string;
  year: string;
  status: 'complete' | 'missing' | 'failed';
  response?: {locus?: Array<{gpsAddress?: string; addTime?: string}>; [key: string]: unknown};
  error?: string;
}

export interface Manifest {
  version: number;
  exportedAt: string;
  rideFile: string;
  routeFiles: Array<{year: string; file: string; count: number}>;
  counts: {rides: number; complete: number; missing: number; failed: number};
}

export interface RideView {
  id: string;
  raw: RawRide;
  start: Date;
  end: Date | null;
  duration: number;
  billedMinutes: number;
  distanceKm: number;
  paidNok: number;
  payableNok: number;
  startPosition: Position | null;
  endPosition: Position | null;
  path: Position[];
  hasTrace: boolean;
  weekday: number;
  hour: number;
  month: string;
  year: string;
  originCell: string;
  destinationCell: string;
  corridor: string;
  commute: boolean;
}

export interface Filters {
  from: string;
  to: string;
  dayType: 'all' | 'weekday' | 'weekend' | 'commute';
  routeDetail: 'all' | 'trace' | 'fallback';
  minMinutes: number;
  maxMinutes: number;
  minCost: number;
  maxCost: number;
  query: string;
  bucket: 'year' | 'month' | 'weekday' | 'hour' | 'duration' | 'cost' | 'origin' | 'corridor';
}
