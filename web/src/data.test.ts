import {describe, expect, it} from 'vitest';
import {parsePosition} from './data';
import {filterRides} from './filter';
import type {Filters, RideView} from './types';

describe('Ryde coordinate parsing', () => {
  it('parses the API longitude,latitude order', () => {
    expect(parsePosition('10,20')).toEqual([10, 20]);
  });
  it('rejects malformed and out-of-range points', () => {
    expect(parsePosition('')).toBeNull();
    expect(parsePosition('500,60')).toBeNull();
  });
});

describe('crossfilters', () => {
  const base: Filters = {from: '', to: '', dayType: 'all', routeDetail: 'all', minMinutes: 0, maxMinutes: 180, minCost: 0, maxCost: 500, query: '', bucket: 'month'};
  const ride = {start: new Date('2026-08-24T08:00:00'), weekday: 1, duration: 17, paidNok: 50, commute: true, hasTrace: true, raw: {startAdd: 'Work'}, id: '1'} as RideView;
  it('combines commute, duration, cost and text predicates', () => {
    expect(filterRides([ride], {...base, dayType: 'commute', minMinutes: 15, maxCost: 60, query: 'work'})).toHaveLength(1);
    expect(filterRides([ride], {...base, dayType: 'weekend'})).toHaveLength(0);
    expect(filterRides([ride], {...base, minMinutes: 18})).toHaveLength(0);
  });
  it('separates full traces from endpoint fallbacks', () => {
    const fallback = {...ride, id: '2', hasTrace: false};
    expect(filterRides([ride, fallback], {...base, routeDetail: 'trace'}).map((item) => item.id)).toEqual(['1']);
    expect(filterRides([ride, fallback], {...base, routeDetail: 'fallback'}).map((item) => item.id)).toEqual(['2']);
  });
});
