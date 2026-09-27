import Icon from './Icon';

/** Tarjeta de indicador. Compartida entre vistas: vivía solo dentro de
 * AeroTrack.tsx, así que el resumen de KPIs del panel de monitoreo tenía que
 * reinventar su propia versión en vez de reutilizar esta. */
export default function Metric({label,value,icon,note,tone='blue'}:{label:string;value:string|number;icon:string;note?:string;tone?:string}) {
  return <article className={`metric-card metric-${tone}`}>
    <span className="metric-icon"><Icon name={icon} size={21}/></span>
    <div className="metric-copy"><span>{label}</span><strong className={`text-${tone}`}>{value}</strong>{note&&<small>{note}</small>}</div>
    <i className="metric-state" aria-hidden="true" />
  </article>;
}
