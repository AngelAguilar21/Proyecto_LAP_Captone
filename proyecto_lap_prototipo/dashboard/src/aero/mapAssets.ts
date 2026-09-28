// Share immutable floor data between the editor and monitoring views.
const assets=new Map<string,Promise<any>>();
export interface MapPlace {id:string;name:string;point:[number,number];asset:string;category:string}
export function businessPlaces(data:any,asset:string):MapPlace[]{
  return (data.features||[]).filter((f:any)=>f.geometry?.type==='Point'&&f.properties?.name&&['retail','food_and_drink'].includes(f.properties.class)).map((f:any)=>({id:String(f.id),name:f.properties.name,point:f.geometry.coordinates,asset,category:f.properties.class}));
}
export function loadMapAsset(url:string):Promise<any>{
  let request=assets.get(url);
  if(!request){
    request=fetch(url).then(r=>{if(!r.ok)throw Error('No se pudo cargar el plano');return r.json();}).catch(error=>{assets.delete(url);throw error;});
    assets.set(url,request);
  }
  return request;
}
