import {weekdayName} from './data';
import type {Filters, RideView} from './types';

export function filterRides(rides: RideView[], filters: Filters): RideView[] {
  const from = filters.from ? new Date(`${filters.from}T00:00:00`).getTime() : -Infinity;
  const to = filters.to ? new Date(`${filters.to}T23:59:59`).getTime() : Infinity;
  const query = filters.query.trim().toLowerCase();
  return rides.filter((ride) => {
    const weekend = ride.weekday === 0 || ride.weekday === 6;
    if (ride.start.getTime() < from || ride.start.getTime() > to) return false;
    if (filters.dayType === 'weekday' && weekend) return false;
    if (filters.dayType === 'weekend' && !weekend) return false;
    if (filters.dayType === 'commute' && !ride.commute) return false;
    if (filters.routeDetail === 'trace' && !ride.hasTrace) return false;
    if (filters.routeDetail === 'fallback' && ride.hasTrace) return false;
    if (ride.duration < filters.minMinutes || ride.duration > filters.maxMinutes) return false;
    if (ride.paidNok < filters.minCost || ride.paidNok > filters.maxCost) return false;
    if (query && !`${ride.raw.startAdd ?? ''} ${ride.raw.endAdd ?? ''} ${ride.id}`.toLowerCase().includes(query)) return false;
    return true;
  });
}

export function bucketValue(ride: RideView, bucket: Filters['bucket']): string {
  if (bucket === 'year') return ride.year;
  if (bucket === 'month') return ride.month;
  if (bucket === 'weekday') return weekdayName(ride.weekday);
  if (bucket === 'hour') return `${String(ride.hour).padStart(2, '0')}:00`;
  if (bucket === 'duration') return ride.duration < 10 ? '<10m' : ride.duration < 15 ? '10–15m' : ride.duration < 20 ? '15–20m' : ride.duration < 30 ? '20–30m' : '30m+';
  if (bucket === 'cost') return ride.paidNok === 0 ? 'Pass/zero' : ride.paidNok < 50 ? '<NOK50' : ride.paidNok < 100 ? 'NOK50–99' : 'NOK100+';
  if (bucket === 'origin') return ride.originCell;
  return ride.corridor;
}
