import { useEffect, useState } from 'react';
import type { Point } from './types';

export interface Business {
  id:string; nombre:string; estado?:string;
  puertas:{camaraId:string;lineaId:string}[];
  ubicacion:{planId:string;point:Point}|null;
  referencia?:{asset:string;featureId:string}|null;
}
export function useBusinesses(scope:string) {
  const [items,setItems]=useState<Business[]>([]);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  useEffect(()=>{
    let active=true;
    const controller=new AbortController();
    async function load() {
      setLoading(true);
      try {
        const response=await fetch('/api/businesses',{headers:{'X-LAP-Session':localStorage.getItem('aero.session')||''},signal:controller.signal});
        const data=await response.json();
        if(!response.ok)throw new Error(data.error||'No se pudieron cargar los negocios.');
        if(active){setItems(data.negocios);setError('');}
      } catch(e){if(active)setError(e instanceof Error?e.message:'No se pudieron cargar los negocios.');}
      finally{if(active)setLoading(false);}
    }
    setItems([]);void load();
    window.addEventListener('aero:businesses',load);
    return()=>{active=false;controller.abort();window.removeEventListener('aero:businesses',load);};
  },[scope]);
  return {items,setItems,error,loading};
}
