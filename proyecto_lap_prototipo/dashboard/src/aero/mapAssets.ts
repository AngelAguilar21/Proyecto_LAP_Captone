// Share immutable floor data between the editor and monitoring views.
const assets=new Map<string,Promise<any>>();
export function loadMapAsset(url:string):Promise<any>{
  let request=assets.get(url);
  if(!request){
    request=fetch(url).then(r=>{if(!r.ok)throw Error('No se pudo cargar el plano');return r.json();}).catch(error=>{assets.delete(url);throw error;});
    assets.set(url,request);
  }
  return request;
}
