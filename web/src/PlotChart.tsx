import * as Plot from '@observablehq/plot';
import {useEffect, useRef} from 'react';
import type {RideView} from './types';

export function PlotChart({rides, kind}: {rides: RideView[]; kind: 'duration' | 'cost' | 'month'}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const value = kind === 'duration' ? (ride: RideView) => ride.duration
      : kind === 'cost' ? (ride: RideView) => ride.paidNok : (ride: RideView) => ride.month;
    const label = kind === 'duration' ? 'Duration (minutes)' : kind === 'cost' ? 'Paid (NOK)' : 'Month';
    const monthly = kind === 'month'
      ? Array.from(rides.reduce((counts, ride) => counts.set(ride.month, (counts.get(ride.month) ?? 0) + 1), new Map<string, number>()))
        .map(([month, count]) => ({month, count}))
      : [];
    const chart = Plot.plot({
      width: Math.max(280, ref.current.clientWidth), height: 170,
      marginLeft: 42, marginBottom: 38,
      style: {background: 'transparent', color: '#d9e2dc', fontFamily: 'Inter, system-ui'},
      x: kind === 'month'
        ? {label, tickFormat: (value) => monthly.findIndex((item) => item.month === value) % 12 === 0 ? value : ''}
        : {label, ticks: 6},
      y: {label: 'Rides', grid: true},
      marks: kind === 'month'
        ? [Plot.barY(monthly, {x: 'month', y: 'count', fill: '#68de3f', tip: true})]
        : [Plot.rectY(rides, {...Plot.binX({y: 'count'}, {x: value, thresholds: 18}), fill: '#68de3f', tip: true} as Plot.RectYOptions)],
    });
    ref.current.replaceChildren(chart);
    return () => chart.remove();
  }, [rides, kind]);
  return <div className="plot" ref={ref} />;
}
