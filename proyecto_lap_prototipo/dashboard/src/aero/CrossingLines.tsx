import type {Camera} from './types';

export default function CrossingLines({lines, crossings, time}: {
  lines: NonNullable<Camera['countLines']>;
  crossings: {id:string;events?:{t:number;direction:string}[]}[];
  time: number;
}) {
  return <>{lines.map(line => {
    const recent = crossings.find(c => c.id === line.id)?.events?.filter(e => time >= e.t && time - e.t < .8) || [];
    const entry = recent.some(e => e.direction === 'entries');
    const exit = recent.some(e => e.direction === 'exits');
    const color = entry && exit ? '#d66add' : entry ? '#36ec9a' : exit ? '#53b6ff' : '#ffcf4b';
    const label = entry && exit ? 'Entrada y salida' : entry ? `Entrada +${recent.filter(e => e.direction === 'entries').length}` : exit ? `Salida +${recent.filter(e => e.direction === 'exits').length}` : line.name;
    return <g key={line.id}><line x1={line.a[0]*100} y1={line.a[1]*100} x2={line.b[0]*100} y2={line.b[1]*100} stroke={color} strokeWidth={recent.length ? .9 : .5}/><text x={line.a[0]*100} y={Math.max(3,line.a[1]*100-1)} fontSize="2.4" fill={color} stroke="#102437" strokeWidth=".12" paintOrder="stroke">{label}</text></g>;
  })}</>;
}
