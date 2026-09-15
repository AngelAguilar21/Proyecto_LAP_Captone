import type {Config,Plan} from './types';

export function snapshotPlan(c:Config):Plan {
  const {width,height,unit,background,floor,zones,workArea,planLines,mapConfigured,mapAsset,planName}=c;
  return {width,height,unit,background,floor:floor||'Espacio de pruebas',zones,workArea,planLines,mapConfigured,mapAsset,planName};
}

export default function PlanSelector({config,onChange,disabled=false}:{config:Config;onChange:(c:Config)=>void;disabled?:boolean}){
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
    onChange({...config,mapAsset:undefined,workArea:undefined,planLines:[],planName:undefined,...next,planId:id,plans,setupComplete:false});
  }
  return <label className="plan-selector">Espacio y nivel<select disabled={disabled} value={config.planId||'custom'} onChange={e=>void select(e.target.value).catch(error=>alert(error.message))}>{(!config.planId||config.planId==='custom'||config.plans?.custom)&&<option value="custom">Espacio de pruebas / plano propio</option>}{[1,2,3,4].map(n=><option key={n} value={`lap-${n}`}>LAP · Nivel {n}{n===3?' · Principal':''}</option>)}</select></label>;
}
