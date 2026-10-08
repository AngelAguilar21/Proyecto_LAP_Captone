// Executable in a real browser. Uses the production hook AND PlanWorkspace
// caller; only HTTP is simulated. No cameras, accounts, or application stores.
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import PlanWorkspace from '../src/aero/PlanWorkspace';
import SecurityAlerts from '../src/aero/SecurityAlerts';
import { useSession } from '../src/aero/useSession';
import { EMPTY_STATE } from '../src/aero/types';
import type { Config } from '../src/aero/types';
import { geometryReady } from '../src/aero/setupReadiness';

(window as any).IS_REACT_ACT_ENVIRONMENT = true;
const initial = { airport:'Original A', floor:'Synthetic', width:12, height:8, unit:'meters',
  background:'', planId:'custom', cameras:[], zones:[], sourceMode:'recordings',
  radius:1, minPeople:2, dwell:2, handoffSeconds:2, matchDistance:1,
  clocksVerified:false, mapConfigured:true, workArea:[[0,0],[12,0],[12,8],[0,8]] } as Config;
const clone = <T,>(value:T):T => JSON.parse(JSON.stringify(value));
let active = 'p-A', revision = 0;
let stored: Record<string,Config>;
let requests: { owner:string; payload:Config; finish:(status?:number)=>void }[];
let ruleRequests: { owner:string; payload:Record<string,unknown>; commit:()=>void; finish:(status?:number)=>void }[];
const withAlertRules = new URLSearchParams(location.search).has('alert-rules');
let session: ReturnType<typeof useSession>;
const nativeFetch=window.fetch.bind(window);
let holdCalibration=false;
let calibrations:{payload:any;release:()=>void}[]=[];
const response = (body:unknown, status=200) => Promise.resolve(new Response(JSON.stringify(body), {status}));
window.fetch = ((url: string, options?:RequestInit) => {
  const path = new URL(url, location.origin);
  if (path.pathname==='/api/calibration-check') {
    const payload=JSON.parse(String(options?.body));
    let release!:()=>void;
    const gate=new Promise<void>(resolve=>{release=resolve;});
    calibrations.push({payload,release});
    if(!holdCalibration)release();
    // Mathematical validation is the actual Python HTTP endpoint. The gate
    // delays delivery only; no frontend imitation of the backend rules.
    return nativeFetch(url,options).then(async result=>{await gate;return result;});
  }
  if (options?.method === 'POST' && path.pathname === '/api/config') {
    const owner = path.searchParams.get('project')!;
    const payload = JSON.parse(String(options.body));
    return new Promise<Response>(resolve => requests.push({ owner, payload, finish:(status=200) => {
      if (status === 200) { stored[owner] = clone(payload); revision++; }
      resolve(new Response(JSON.stringify(status === 200 ? {ok:true} : {error:'Synthetic save rejected'}), {status}));
    }}));
  }
  if (options?.method === 'POST' && path.pathname === '/api/alert-rules') {
    const payload = JSON.parse(String(options.body));
    const {projectId:owner,...rules} = payload;
    return new Promise<Response>(resolve => ruleRequests.push({owner,payload,
      commit:()=>{stored[owner]={...stored[owner],...rules};revision++;},
      finish:(status=200)=>resolve(new Response(JSON.stringify(status===200?{ok:true}:{error:'Synthetic rules rejected'}),{status})),
    }));
  }
  if (options?.method === 'POST' && path.pathname === '/api/projects') {
    active = JSON.parse(String(options.body)).id; revision++;
  }
  switch (path.pathname) {
    case '/api/state': return response({...EMPTY_STATE, serverInstance:'browser-regression', configRevision:revision});
    case '/api/config': return response({config:clone(stored[active]), projectId:active, revision, token:'synthetic'});
    case '/api/projects': return response({active, projects:Object.keys(stored).map(id=>({id,name:id}))});
    case '/api/auth': return response({configurado:true, usuario:'synthetic', rol:'operador', usuarios:[]});
    case '/api/incidents': return response({incidentes:[]});
    case '/api/mail': return response({enabled:false,recipients:[],configured:false,host:'',port:587,user:''});
    default: return response({error:'Unexpected test request: '+path.pathname},404);
  }
}) as typeof fetch;

function Fixture() {
  session = useSession();
  if (!session.config) return <p>Loading synthetic session</p>;
  return <>
    <label>Proyecto <input aria-label="Proyecto" value={session.config.airport}
      onChange={event=>session.setConfig({...session.config!,airport:event.target.value})}/></label>
    <output id="draft-status">{session.saving?'saving':session.dirty?'pending':'saved'}</output>
    <output id="notice">{session.notice}</output><output id="error">{session.error}</output>
    <button onClick={()=>void session.action(async()=>{await session.save();})}>Guardar borrador</button>
    <button onClick={()=>void session.projectAction('open',{id:'p-B'})}>Abrir B</button>
    <label>Ancho <input aria-label="Ancho" type="number" value={session.config.width}
      onChange={e=>session.setConfig({...session.config!,width:Number(e.target.value)})}/></label>
    <output id="geometry-readiness">{session.config.cameras[0]&&geometryReady(session.config.cameras[0],session.calibrationFor(session.config.cameras[0]))?'Preparado':'Pendiente'}</output>
    <PlanWorkspace session={session} selected={session.config.cameras[0]?.id||''} onSelected={()=>{}} startTest={()=>{throw Error('Inference forbidden');}} section={session.config.cameras.length?'calibration':'area'} embedded/>
    {withAlertRules&&<SecurityAlerts key={session.projects.active||'none'} session={session} onOpenCamera={()=>{throw Error('Capture forbidden');}}/>}
  </>;
}
const results: {name:string; ok:boolean; detail?:string}[] = [];
const target = document.getElementById('root')!;
let root: ReturnType<typeof createRoot>;
const expect = (condition:unknown, detail:string) => {if(!condition)throw Error(detail);};
const tick = () => new Promise<void>(resolve=>setTimeout(resolve,0));
async function until(check:()=>boolean) {
  const deadline = performance.now()+5000;
  while(!check()) {if(performance.now()>deadline)throw Error('Browser fixture did not settle');await act(tick);}
}
async function click(label:string) {
  const button = [...target.querySelectorAll('button')].find(button=>button.textContent===label)!;
  expect(button&&!button.disabled,'Missing/enabled button: '+label);
  await act(async()=>{button.click();await tick();});
}
async function edit(value:string) {
  await act(async()=>{
    const input=target.querySelector('input[aria-label="Proyecto"]')!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,value);
    input.dispatchEvent(new Event('input',{bubbles:true}));await tick();
  });
}
async function pendingAreaSave() {
  await click('Ajustar límite');await click('Guardar límite');await until(()=>requests.length===1);
  expect(requests[0].payload.airport==='Original A','Frozen payload before newer edit');
}
async function run(name:string, operation:()=>Promise<void>) {
  active='p-A';revision=0;stored={'p-A':clone(initial),'p-B':{...clone(initial),airport:'Project B'}};requests=[];ruleRequests=[];calibrations=[];holdCalibration=false;
  root=createRoot(target);
  try {
    await act(async()=>{root.render(<Fixture/>);await tick();});
    await until(()=>!!session.config&&session.auth.cargado&&session.projects.active==='p-A');
    await operation();results.push({name,ok:true});
  } catch(error) {results.push({name,ok:false,detail:String(error)});}
  finally {await act(async()=>{root.unmount();await tick();});}
  document.getElementById('results')!.textContent=JSON.stringify(results,null,2);
}
await run('real caller preserves a newer draft, then persists it on a later save',async()=>{
  await pendingAreaSave();await edit('NEWER DRAFT');
  expect(session.config!.airport==='NEWER DRAFT','Newer edit reached React');
  await act(async()=>{requests[0].finish();await tick();});
  await until(()=>!session.busy&&!session.saving);
  expect(session.config!.airport==='NEWER DRAFT','Late caller overwrote newer edit');
  expect(session.dirty&&target.querySelector('#draft-status')!.textContent==='pending','Unsent edit must remain pending');
  expect(stored['p-A'].airport==='Original A','First response only saved its captured version');
  await click('Guardar borrador');await until(()=>requests.length===2);
  expect(requests[1].payload.airport==='NEWER DRAFT','Second request contains newer edit');
  await act(async()=>{requests[1].finish();await tick();});
  await until(()=>!session.saving&&!session.busy);
  expect(!session.dirty&&stored['p-A'].airport==='NEWER DRAFT','Later save confirmed exactly the newer version');
});
await run('rejected limit save keeps the later draft and visible error',async()=>{
  await pendingAreaSave();await edit('DRAFT AFTER REJECTION');
  await act(async()=>{requests[0].finish(400);await tick();});
  await until(()=>!session.busy&&!session.saving);
  expect(session.config!.airport==='DRAFT AFTER REJECTION'&&session.dirty,'Rejection discarded draft');
  expect(session.error==='Synthetic save rejected'&&!session.notice,'Failure displayed as success');
  expect(stored['p-A'].airport==='Original A','Rejected request changed stored config');
});
await run('late successful response from A never confirms or replaces B',async()=>{
  await pendingAreaSave();await click('Abrir B');await until(()=>session.config!.airport==='Project B');
  await act(async()=>{requests[0].finish();await tick();});
  await until(()=>!session.busy&&!session.saving);
  expect(session.config!.airport==='Project B','A response replaced project B');
  expect(!session.notice&&!session.dirty,'A response confirmed unrelated project');
  expect(stored['p-B'].airport==='Project B','B store changed');
});
if(withAlertRules) {
  async function pendingRulesSave() {
    await act(async()=>{
      const input=target.querySelector('.rules-form input[type="number"]')!;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'7');
      input.dispatchEvent(new Event('input',{bubbles:true}));await tick();
    });
    await click('Guardar umbrales');await until(()=>ruleRequests.length===1);
    expect(ruleRequests[0].owner==='p-A','Rules request omitted the intended project');
    expect(ruleRequests[0].payload.minPeople===7,'Rules request omitted the edited value');
    expect(!('cameras' in ruleRequests[0].payload),'Rules request must not send the complete configuration');
  }
  await run('real alert-rules caller sends project identity and confirms its own save',async()=>{
    await pendingRulesSave();
    await act(async()=>{ruleRequests[0].commit();ruleRequests[0].finish();await tick();});
    await until(()=>!session.busy);
    expect(session.notice==='Umbrales de alerta actualizados.','Own successful rules save was not confirmed');
    expect(stored['p-A'].minPeople===7&&stored['p-B'].minPeople===2,'Rules changed the wrong project');
  });
  await run('late successful rules response from A cannot confirm project B',async()=>{
    await pendingRulesSave();
    // A accepted the update before B opened, but its HTTP response is delayed.
    await act(async()=>{ruleRequests[0].commit();await tick();});
    await click('Abrir B');await until(()=>session.config!.airport==='Project B'&&session.projects.active==='p-B');
    await act(async()=>{ruleRequests[0].finish();await tick();});
    await until(()=>!session.busy);
    expect(session.notice!== 'Umbrales de alerta actualizados.','Old rules response confirmed B');
    expect(!session.error,'Old successful rules response generated an error in B');
    expect(session.config!.airport==='Project B'&&stored['p-B'].minPeople===2,'Old rules response replaced B');
    expect(target.querySelector<HTMLInputElement>('.rules-form input[type="number"]')!.value==='2','B shows A rules draft');
  });
  await run('late rejected rules response from A cannot replace feedback in B',async()=>{
    await pendingRulesSave();await click('Abrir B');
    await until(()=>session.config!.airport==='Project B'&&session.projects.active==='p-B');
    await act(async()=>{session.setNotice('Project B context');ruleRequests[0].finish(400);await tick();});
    await until(()=>!session.busy);
    expect(!session.error&&session.notice==='Project B context','Old rules rejection contaminated B feedback');
    expect(stored['p-A'].minPeople===2&&stored['p-B'].minPeople===2,'Rejected rules request changed a store');
  });
}
if(new URLSearchParams(location.search).has('calibration')) {
  const camera={id:'C',source:'synthetic.mp4',x:1,y:1,offset:0,links:[],height:3,planId:'custom',
    pairs:[[0,0,0,0],[1,0,12,0],[1,1,12,8],[0,1,0,8]]};
  const check=()=>session.calibrationFor(session.config!.cameras[0]);
  await run('real HTTP rejects x=12.5 for a 12x8 plan while React preserves the draft',async()=>{
    const outside={...camera,pairs:camera.pairs.map(([u,v,x,y])=>[u,v,x===12?12.5:x,y])};
    await act(async()=>{session.setConfig({...session.config!,cameras:[outside]});await tick();});
    await until(()=>['valid','invalid','unavailable'].includes(check()?.status||''));
    expect(check()?.status==='invalid','Out-of-plan geometry incorrectly prepared');
    expect(target.querySelector('#geometry-readiness')!.textContent==='Pendiente','Invalid geometry marked ready');
    expect(check()!.message?.includes('fuera'),'Concrete backend rejection missing');
    expect(session.config!.cameras[0].pairs[1][2]===12.5&&session.dirty,'Rejected calibration discarded draft');
    expect(stored['p-A'].cameras.length===0,'Validation mutated saved configuration');
  });
  await run('dimension edit invalidates readiness and late valid answer cannot revive it',async()=>{
    await act(async()=>{session.setConfig({...session.config!,cameras:[clone(camera)]});await tick();});
    await until(()=>check()?.status==='valid');
    expect(target.querySelector('#geometry-readiness')!.textContent==='Preparado','Valid control not prepared');
    holdCalibration=true;
    let older:Promise<unknown>;
    await act(async()=>{older=session.validateCalibration('C').catch(e=>e);await tick();});
    await until(()=>calibrations.length===2);
    await act(async()=>{
      const input=target.querySelector('input[aria-label="Ancho"]')!;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'11');
      input.dispatchEvent(new Event('input',{bubbles:true}));await tick();
    });
    expect(target.querySelector('#geometry-readiness')!.textContent==='Pendiente','Old dimensions still prepared');
    await until(()=>calibrations.length===3);
    expect(calibrations[2].payload.context.width===11,'Request omitted current dimensions');
    await act(async()=>{calibrations[2].release();await tick();});
    await until(()=>check()?.status==='invalid');
    await act(async()=>{calibrations[1].release();await older!;await tick();});
    expect(check()?.status==='invalid'&&session.config!.width===11,'Late answer restored old readiness or draft');
  });
}
document.body.dataset.result=results.every(result=>result.ok)?'PASS':'FAIL';
document.title='AUD-05/08 / REV-01 '+document.body.dataset.result;
