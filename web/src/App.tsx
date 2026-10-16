import {ArcLayer, PathLayer, ScatterplotLayer} from '@deck.gl/layers';
import {DeckGL} from '@deck.gl/react';
import {WebMercatorViewport, type PickingInfo} from '@deck.gl/core';
import MapGL from 'react-map-gl/maplibre';
import {setWorkerUrl} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import {useEffect, useMemo, useState} from 'react';
import 'maplibre-gl/dist/maplibre-gl.css';
import './legend.css';
import {loadDataset, weekdayName} from './data';
import {bucketValue, filterRides} from './filter';
import {PlotChart} from './PlotChart';
import {RydeLogo} from './RydeLogo';
import type {Filters, Manifest, RideView} from './types';

setWorkerUrl(workerUrl);

const palette = ['#68de3f', '#78ccff', '#ffcb69', '#f39ac2', '#9f8cff', '#ff907d', '#abef94', '#45d7c4'];
const initialFilters: Filters = {from: '', to: '', dayType: 'all', routeDetail: 'all', minMinutes: 0, maxMinutes: 180, minCost: 0, maxCost: 500, query: '', bucket: 'month'};

function hash(value: string): number {
  let result = 0;
  for (let index = 0; index < value.length; index += 1) result = ((result << 5) - result + value.charCodeAt(index)) | 0;
  return Math.abs(result);
}

function color(ride: RideView, bucket: Filters['bucket'], alpha = 210): [number, number, number, number] {
  const hex = palette[hash(bucketValue(ride, bucket)) % palette.length];
  return [Number.parseInt(hex.slice(1, 3), 16), Number.parseInt(hex.slice(3, 5), 16), Number.parseInt(hex.slice(5, 7), 16), alpha];
}

export default function App() {
  const [rides, setRides] = useState<RideView[]>([]);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [loading, setLoading] = useState('Loading manifest…');
  const [error, setError] = useState('');
  const [filters, setFilters] = useState<Filters>(() => {
    try { return {...initialFilters, ...JSON.parse(new URLSearchParams(location.search).get('filters') ?? '{}')}; } catch { return initialFilters; }
  });
  const [selected, setSelected] = useState<RideView | null>(null);
  const [panel, setPanel] = useState(true);
  const [showPoints, setShowPoints] = useState(false);

  useEffect(() => { loadDataset(setLoading).then(({manifest: loadedManifest, rides: loadedRides}) => { setManifest(loadedManifest); setRides(loadedRides); setLoading(''); }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason))); }, []);
  useEffect(() => {
    const url = new URL(location.href);
    url.searchParams.set('filters', JSON.stringify(filters));
    history.replaceState(null, '', url);
  }, [filters]);
  const filtered = useMemo(() => filterRides(rides, filters), [rides, filters]);
  const initialView = useMemo(() => {
    const points = rides.flatMap((ride) => [ride.startPosition, ride.endPosition]).filter((point) => point !== null);
    if (!points.length) return {longitude: 0, latitude: 0, zoom: 1, pitch: 0, bearing: 0};
    const longitudes = points.map((point) => point[0]);
    const latitudes = points.map((point) => point[1]);
    const bounds: [[number, number], [number, number]] = [[Math.min(...longitudes), Math.min(...latitudes)], [Math.max(...longitudes), Math.max(...latitudes)]];
    const fitted = new WebMercatorViewport({width: Math.max(320, window.innerWidth - 300), height: Math.max(480, window.innerHeight * 0.64)}).fitBounds(bounds, {padding: 80, maxZoom: 15});
    return {longitude: fitted.longitude, latitude: fitted.latitude, zoom: fitted.zoom, pitch: 0, bearing: 0};
  }, [rides]);
  const traced = useMemo(() => filtered.filter((ride) => ride.hasTrace), [filtered]);
  const fallback = useMemo(() => filtered.filter((ride) => !ride.hasTrace && ride.startPosition && ride.endPosition), [filtered]);
  const totalKm = filtered.reduce((sum, ride) => sum + ride.distanceKm, 0);
  const totalPaid = filtered.reduce((sum, ride) => sum + ride.paidNok, 0);
  const totalMinutes = filtered.reduce((sum, ride) => sum + ride.duration, 0);
  const bucketSummary = useMemo(() => {
    const counts = new Map<string, number>();
    filtered.forEach((ride) => { const bucket = bucketValue(ride, filters.bucket); counts.set(bucket, (counts.get(bucket) ?? 0) + 1); });
    return [...counts].map(([bucket, count]) => ({bucket, count})).sort((left, right) => right.count - left.count).slice(0, 6);
  }, [filtered, filters.bucket]);
  const layers = [
    new PathLayer<RideView>({id: 'routes', data: traced, getPath: (ride) => ride.path, getColor: (ride) => color(ride, filters.bucket, selected?.id === ride.id ? 255 : 175), getWidth: (ride) => selected?.id === ride.id ? 7 : 3, widthUnits: 'pixels', widthMinPixels: 1, pickable: true, autoHighlight: true}),
    new ArcLayer<RideView>({id: 'fallback-arcs', data: fallback, getSourcePosition: (ride) => ride.startPosition!, getTargetPosition: (ride) => ride.endPosition!, getSourceColor: (ride) => color(ride, filters.bucket, 180), getTargetColor: (ride) => color(ride, filters.bucket, 80), getWidth: 2, widthUnits: 'pixels', pickable: true}),
    ...(showPoints ? [new ScatterplotLayer<RideView>({id: 'starts', data: filtered.filter((ride) => ride.startPosition), getPosition: (ride) => ride.startPosition!, getFillColor: [104, 222, 63, 170], getRadius: 16, radiusUnits: 'meters', pickable: true})] : []),
  ];
  const select = (info: PickingInfo<RideView>) => { if (info.object) setSelected(info.object); };
  const update = <K extends keyof Filters>(key: K, value: Filters[K]) => setFilters((current) => ({...current, [key]: value}));
  const savePreset = () => { localStorage.setItem('ryde-stats-preset', JSON.stringify(filters)); };
  const loadPreset = () => { const value = localStorage.getItem('ryde-stats-preset'); if (value) setFilters({...initialFilters, ...JSON.parse(value)}); };

  if (error) return <main className="state"><RydeLogo/><h1>Data could not be loaded</h1><p>{error}</p><p>Prepare your data and open a new dashboard with the Ryde CLI.</p></main>;
  if (loading) return <main className="state"><RydeLogo/><div className="loader"/><p>{loading}</p></main>;
  return <div className="app">
    <header><RydeLogo/><span className="product">STATS</span><div className="header-meta">{manifest?.counts.rides.toLocaleString()} rides · {manifest?.counts.complete.toLocaleString()} full traces</div><button onClick={() => setPanel((value) => !value)}>{panel ? 'Hide filters' : 'Show filters'}</button></header>
    <section className="metrics"><div><b>{filtered.length.toLocaleString()}</b><span>rides</span></div><div><b>{Math.round(totalMinutes).toLocaleString()}</b><span>minutes</span></div><div><b>{totalKm.toFixed(1)}</b><span>kilometres</span></div><div><b>NOK {totalPaid.toFixed(0)}</b><span>paid</span></div><div><b>{filtered.filter((ride) => ride.commute).length}</b><span>commute-like</span></div></section>
    <main className={panel ? 'with-panel' : ''}>
      {panel && <aside className="filters">
        <div className="filter-title"><h2>Crossfilter</h2><button className="quiet" onClick={() => setFilters(initialFilters)}>Reset</button></div>
        <label>Search raw IDs or addresses<input value={filters.query} onChange={(event) => update('query', event.target.value)} placeholder="Address, ID…" /></label>
        <div className="pair"><label>From<input type="date" value={filters.from} onChange={(event) => update('from', event.target.value)} /></label><label>To<input type="date" value={filters.to} onChange={(event) => update('to', event.target.value)} /></label></div>
        <label>Ride type<select value={filters.dayType} onChange={(event) => update('dayType', event.target.value as Filters['dayType'])}><option value="all">All rides</option><option value="weekday">Weekdays</option><option value="weekend">Weekends</option><option value="commute">Inferred commute</option></select></label>
        <label>Route detail<select value={filters.routeDetail} onChange={(event) => update('routeDetail', event.target.value as Filters['routeDetail'])}><option value="all">All route types</option><option value="trace">Full GPS traces only</option><option value="fallback">Endpoint fallbacks only</option></select></label>
        <label>Colour and bucket by<select value={filters.bucket} onChange={(event) => update('bucket', event.target.value as Filters['bucket'])}><option value="month">Month</option><option value="year">Year</option><option value="weekday">Weekday</option><option value="hour">Hour</option><option value="duration">Duration band</option><option value="cost">Cost band</option><option value="origin">Origin H3 cell</option><option value="corridor">Recurring corridor</option></select></label>
        <label>Duration: {filters.minMinutes}–{filters.maxMinutes} min<div className="pair sliders"><input type="range" min="0" max="180" value={filters.minMinutes} onChange={(event) => update('minMinutes', Number(event.target.value))}/><input type="range" min="0" max="180" value={filters.maxMinutes} onChange={(event) => update('maxMinutes', Number(event.target.value))}/></div></label>
        <label>Paid: NOK {filters.minCost}–{filters.maxCost}<div className="pair sliders"><input type="range" min="0" max="500" value={filters.minCost} onChange={(event) => update('minCost', Number(event.target.value))}/><input type="range" min="0" max="500" value={filters.maxCost} onChange={(event) => update('maxCost', Number(event.target.value))}/></div></label>
        <label className="check"><input type="checkbox" checked={showPoints} onChange={(event) => setShowPoints(event.target.checked)}/> Show origin points</label>
        <div className="preset"><button onClick={savePreset}>Save preset</button><button onClick={loadPreset}>Load preset</button></div>
        <p className="hint">Commute-like means a weekday ride on a corridor seen at least ten times in both directions.</p>
      </aside>}
      <section className="map-wrap">
        <DeckGL initialViewState={initialView} controller layers={layers} onClick={select} getTooltip={({object}: PickingInfo<RideView>) => object ? `${object.start.toLocaleString()}\n${object.duration.toFixed(1)} min · ${object.distanceKm.toFixed(2)} km · NOK ${object.paidNok.toFixed(2)}` : null}>
          <MapGL mapStyle="https://tiles.openfreemap.org/styles/liberty" />
        </DeckGL>
        <div className="bucket-key">{bucketSummary.map((item) => <div key={item.bucket}><i style={{background: palette[hash(item.bucket) % palette.length]}}/><span>{item.bucket}</span><b>{item.count}</b></div>)}</div>
        <div className="map-key"><span className="trace"/> Full trace <span className="arc"/> endpoint fallback</div>
      </section>
      <section className="analytics">
        <article><h3>Duration distribution</h3><PlotChart rides={filtered} kind="duration"/></article>
        <article><h3>Paid-cost distribution</h3><PlotChart rides={filtered} kind="cost"/></article>
        <article className="wide"><h3>Rides over time</h3><PlotChart rides={filtered} kind="month"/></article>
      </section>
    </main>
    {selected && <div className="backdrop" onClick={() => setSelected(null)}><section className="drawer" onClick={(event) => event.stopPropagation()}><button className="close" onClick={() => setSelected(null)}>×</button><p className="eyebrow">Ride {selected.id}</p><h2>{selected.raw.startAdd ? String(selected.raw.startAdd) : 'Recorded ride'}</h2><p>{selected.start.toLocaleString()} · {weekdayName(selected.weekday)}</p><div className="drawer-stats"><b>{selected.duration.toFixed(1)} min</b><b>{selected.distanceKm.toFixed(2)} km</b><b>NOK {selected.paidNok.toFixed(2)}</b></div><p>{selected.hasTrace ? `${selected.path.length} recorded route points` : 'Endpoint fallback — no stored route trace'}</p><h3>Raw record</h3><pre>{JSON.stringify(selected.raw, null, 2)}</pre></section></div>}
  </div>;
}
