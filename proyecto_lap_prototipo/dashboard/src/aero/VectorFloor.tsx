import {loadMapAsset} from './mapAssets';
import type {MapPlace} from './mapAssets';
import {memo,useEffect,useState} from 'react';
type Geometry={type:string;coordinates:any};
type Feature={id:string;geometry:Geometry;properties:{name?:string;class?:string;type?:string;category?:string;is_label_shown?:boolean;local_rank?:number}};
function VectorFloor({asset,scale,bearing=0,onPlace,names={}}:{asset:string;scale:number;bearing?:number;onPlace?:(place:MapPlace)=>void;names?:Record<string,string>}){
  const [features,setFeatures]=useState<Feature[]>([]);
  useEffect(()=>{let alive=true;setFeatures([]);void loadMapAsset(asset).then(d=>{if(alive)setFeatures(d.features);}).catch(()=>{});return()=>{alive=false;};},[asset]);
  const path=(g:Geometry):string=>{
    const line=(p:number[][],close=false)=>p.map((xy,i)=>`${i?'L':'M'}${xy[0]},${xy[1]}`).join(' ')+(close?' Z':'');
    if(g.type==='Polygon')return g.coordinates.map((r:number[][])=>line(r,true)).join(' ');
    if(g.type==='MultiPolygon')return g.coordinates.map((p:number[][][])=>p.map(r=>line(r,true)).join(' ')).join(' ');
    if(g.type==='LineString')return line(g.coordinates);
    if(g.type==='MultiLineString')return g.coordinates.map((r:number[][])=>line(r)).join(' ');
    return '';
  };
  const color=(p:Feature['properties'])=>p.class==='food_and_drink'?'#fae68b':p.class==='retail'?'#d5d2f7':p.class==='restroom'?'#a6dde2':p.type==='floor'||p.type==='corridor'?'#fff':p.type==='vista'?'#e8edef':'#edf0f4';
  return <g className="vector-floor" pointerEvents="none">
    {[...features].sort((a,b)=>(a.properties.type==='floor'?-1:0)-(b.properties.type==='floor'?-1:0)).map((f,i)=>f.geometry.type.includes('Point')?null:<path key={`${f.id}-${i}`} d={path(f.geometry)} fill={f.geometry.type.includes('Polygon')?color(f.properties):'none'} fillRule="evenodd" stroke="#9cafba" strokeWidth={Math.max(.08,scale*.7)}/>) }
    {scale<.9&&features.filter(f=>f.geometry.type==='Point'&&f.properties.name&&(scale<.3||(f.properties.is_label_shown!==false&&(f.properties.local_rank??0)<=3))).map((f,i)=>{const p={...f.properties,name:names[String(f.id)]||f.properties.name},gate=p.type==='gate'||/^Boarding Room [A-Z]\d+$/.test(p.name||''),food=p.class==='food_and_drink',shop=p.class==='retail',toilet=p.class==='restroom';return <g key={`${f.id}-${i}`} transform={`translate(${f.geometry.coordinates[0]} ${f.geometry.coordinates[1]}) rotate(${-bearing}) scale(${scale})`} style={onPlace&&['retail','food_and_drink'].includes(p.class||'')?{pointerEvents:'auto',cursor:'pointer'}:undefined} onPointerDown={e=>{if(onPlace&&['retail','food_and_drink'].includes(p.class||''))e.stopPropagation();}} onPointerUp={e=>{if(onPlace&&['retail','food_and_drink'].includes(p.class||'')){e.stopPropagation();onPlace({id:String(f.id),name:p.name!,point:f.geometry.coordinates,asset,category:p.class!});}}}>
      {gate?<><rect x="-15" y="-12" width="30" height="24" rx="3" fill="#34318a" stroke="white" strokeWidth="1.5"/><text textAnchor="middle" y="4" fontSize="12" fontWeight="700" fill="white">{p.name?.replace(/.*?([A-Z]\d+)$/,'$1')}</text></>:<><circle r="9" fill={food?'#a05212':shop?'#783e9b':toilet?'#087d91':'#547383'}/><path d={food?'M-4 -5V0H0V-5M-2 -5V6M4 -5V6':shop?'M-5 -2H5V6H-5ZM-2 -2V-4Q0 -7 2 -4V-2':toilet?'M0 -4V2M-4 -1H4M0 2L-3 6M0 2L3 6':'M0 -4V4M-4 0H4'} fill="none" stroke="white" strokeWidth="1.5"/><text x="12" y="4" fontSize="11" fill="#273e50" stroke="white" strokeWidth="2.5" paintOrder="stroke">{p.name}</text></>}
    </g>;})}
  </g>;
}

export default memo(VectorFloor);
