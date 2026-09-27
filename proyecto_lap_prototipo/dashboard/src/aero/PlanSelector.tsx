import {useState} from 'react';
import type {Config,Plan} from './types';
import Icon from './Icon';

export function snapshotPlan(c:Config):Plan {
  const {width,height,unit,background,floor,zones,commercialContext,workArea,planLines,mapConfigured,mapAsset,planName,planView}=c;
  return {width,height,unit,background,floor:floor||'Espacio de pruebas',zones,commercialContext,workArea,planLines,mapConfigured,mapAsset,planName,planView};
}

export default function PlanSelector({config,onChange,disabled=false,manage=false}:{config:Config;onChange:(c:Config)=>void;disabled?:boolean;manage?:boolean}){
  const [adding,setAdding]=useState(false);
  const [floorName,setFloorName]=useState('');
  async function select(id:string){
    const plans={...config.plans,[config.planId||'custom']:snapshotPlan(config)};
    let next=plans[id];
    if(!next){
      const level=Number(id.split('-')[1]);
      const response=await fetch(`/maps/lap/${level}.json`);
      if(!response.ok)throw Error('No se pudo abrir el plano local del LAP.');
      const map=await response.json();
      next={width:map.width,height:map.height,unit:'meters',background:'',floor:map.name,zones:[],mapConfigured:true,mapAsset:`/maps/lap/${level}.json`,planLines:[]};
    }
    onChange({...config,mapAsset:undefined,workArea:undefined,planLines:[],planName:undefined,commercialContext:undefined,...next,planId:id,plans,setupComplete:false});
  }
  // Los planos del LAP son material de demostración, no contenido de todo proyecto.
  // Solo se listan si este proyecto ya los usa; si no, hay que pedirlos a propósito,
  // para que un proyecto de otro espacio no muestre niveles de un aeropuerto ajeno.
  const usaLap=(config.planId||'').startsWith('lap-')
    ||Object.keys(config.plans||{}).some(k=>k.startsWith('lap-'))
    ||config.cameras.some(c=>(c.planId||'').startsWith('lap-'));
  const [mostrarLap,setMostrarLap]=useState(false);
  const verLap=usaLap||mostrarLap;
  function addFloor(){
    const name=floorName.trim();
    if(!name)return;
    const current=config.planId||'custom';
    const id=`floor-${crypto.randomUUID().slice(0,8)}`;
    const plans={...config.plans,[current]:snapshotPlan(config)};
    const next:Plan={width:config.width,height:config.height,unit:config.unit,background:'',floor:name,zones:[],mapConfigured:false,planLines:[]};
    plans[id]=next;
    onChange({...config,...next,planId:id,plans,mapAsset:undefined,workArea:undefined,planName:undefined,commercialContext:undefined,setupComplete:false});
    setFloorName('');setAdding(false);
  }
  return <div className="plan-selector-wrap">
    <label className="plan-selector">Piso o nivel<select aria-label="Piso o nivel activo" disabled={disabled} value={config.planId||'custom'} onChange={e=>{if(e.target.value==='__demo__'){setMostrarLap(true);return;}void select(e.target.value).catch(error=>alert(error.message));}}>{(!config.planId||config.planId==='custom'||config.plans?.custom)&&<option value="custom">{config.floor||'Plano principal'}</option>}{Object.keys(config.plans||{}).filter(k=>k!=='custom'&&!k.startsWith('lap-')).map(k=><option key={k} value={k}>{config.plans![k].floor||k}</option>)}{verLap&&[1,2,3,4].map(n=><option key={n} value={`lap-${n}`}>LAP · Nivel {n}{n===3?' · Principal':''}</option>)}{!verLap&&<option value="__demo__">Cargar planos de demostración (LAP)…</option>}</select></label>
    {manage&&!adding&&<button type="button" disabled={disabled} onClick={()=>setAdding(true)}><Icon name="plus" size={15}/>Añadir piso</button>}
    {manage&&adding&&<div className="floor-create" role="group" aria-label="Añadir piso"><label>Nombre del piso<input name="floor-name" autoComplete="off" value={floorName} placeholder="Ejemplo: Terminal A · Nivel 2…" onChange={e=>setFloorName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')addFloor();if(e.key==='Escape')setAdding(false);}}/></label><button className="primary" disabled={!floorName.trim()} onClick={addFloor}>Crear piso</button><button onClick={()=>{setAdding(false);setFloorName('');}}>Cancelar</button></div>}
  </div>;
}
