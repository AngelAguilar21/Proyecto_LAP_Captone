// Run the same state/validation functions consumed by the wizard, without a
// browser, camera, live backend, credentials, or an additional test dependency.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { basename, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const temporary = mkdtempSync(join(tmpdir(), 'aerotrack-calibration-'));
const require = createRequire(import.meta.url);
let passed = 0;
const run = async (name, operation) => { await operation(); passed += 1; console.log(`OK ${name}`); };
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };

try {
  execFileSync(process.execPath, [join(root, 'node_modules/typescript/bin/tsc'),
    'src/aero/calibration.ts', 'src/aero/setupReadiness.ts', 'src/aero/sessionSave.ts',
    '--outDir', temporary, '--module', 'commonjs', '--target', 'es2020', '--moduleResolution', 'node',
    '--strict', '--skipLibCheck'], { cwd: root, stdio: 'pipe' });
  const { ApiError, CalibrationValidator, calibrationKey, currentCalibration, calibrationMessage, isCalibrationError } = require(join(temporary, 'calibration.js'));
  const { projectReadiness } = require(join(temporary, 'setupReadiness.js'));
  const { ConfigSaveQueue, saveWithFeedback, saveStatusLabel } = require(join(temporary, 'sessionSave.js'));
  const scope = { projectId: 'synthetic-project', serverInstance: 'synthetic-server' };
  const diagnostics = { rmse: 0, spread: 1, maxError: 0, pointErrors: [0,0,0,0], validationError: null, validationPoints: 0,
    warning: 'Añade referencias adicionales para comprobar puntos no usados en cada ajuste.' };
  const camera = { id: 'A', planId: 'custom', source: 'synthetic.mp4', x: 0, y: 0, offset: 0, links: [],
    pairs: [[0,0,0,0],[1,0,12,0],[1,1,12,8],[0,1,0,8]], height: 3,
    coverageShape: 'free', coveragePolygon: [[0,0],[12,0],[12,8]], detectionZone: [[0,0],[1,0],[1,1]] };
  const config = { cameras: [camera], planId:'custom', sourceMode:'recordings', mapConfigured:true, airport:'Synthetic', floor:'Test',
    width:12, height:8, unit:'meters', background:'', zones:[], commercialContext:{hasBusinesses:false}, radius:1, minPeople:2,
    dwell:2, handoffSeconds:2, matchDistance:2, clocksVerified:true };
  const state = { sourceChecks: { A: { source:'synthetic.mp4', valid:true } } };
  const ready = (checks, cfg = config, context = scope) => projectReadiness(cfg, state, item => currentCalibration(item, context, checks));
  const geometry = stages => stages.find(stage => stage.step === 'calibrate');
  const crossed = 'La proyección se cruza dentro del área calibrada. Revisa el orden de las correspondencias.';

  await run('sufficient references alone never claim valid geometry', () => {
    assert.equal(geometry(ready({})).done, false);
    assert.match(geometry(ready({})).subtitle, /1\/1 con referencias suficientes/);
    assert.match(geometry(ready({})).subtitle, /0\/1 geometrías válidas/);
    assert.match(calibrationMessage(camera), /sin comprobar/);
  });
  await run('backend-valid geometry enables readiness without claiming independent physical accuracy', async () => {
    let sent; const validator = new CalibrationValidator(async pairs => { sent = pairs; return diagnostics; });
    const checks = await validator.validate([camera], scope, () => {});
    assert.deepEqual(sent, camera.pairs);
    assert.notEqual(sent, camera.pairs);
    assert.equal(ready(checks).every(stage => stage.done), true);
    assert.equal(checks.A.diagnostics.validationPoints, 0);
    assert.match(calibrationMessage(camera, checks.A), /geometría válida según el servidor/);
  });
  await run('backend rejection blocks readiness and preserves the crossed-projection cause', async () => {
    const validator = new CalibrationValidator(async () => { throw new ApiError(crossed, 400); });
    const checks = await validator.validate([camera], scope, () => {});
    assert.equal(checks.A.status, 'invalid');
    assert.equal(checks.A.message, crossed);
    assert.equal(geometry(ready(checks)).done, false);
    assert.match(calibrationMessage(camera, checks.A), /4 referencias colocadas · calibración inválida: La proyección se cruza/);
    assert.equal(isCalibrationError(crossed), true);
  });
  await run('every existing geometry rejection retains its backend explanation', async () => {
    for (const message of ['Hay referencias repetidas. Elimina el punto duplicado.', 'Referencias casi alineadas: distribuye los puntos.',
      'Calibración degenerada: distribuye los puntos.', 'Correspondencias inconsistentes; revisa los puntos.']) {
      const checks = await new CalibrationValidator(async () => { throw new ApiError(message, 400); }).validate([camera], scope, () => {});
      assert.equal(checks.A.message, message);
      assert.equal(geometry(ready(checks)).done, false);
      assert.equal(isCalibrationError(message), true);
    }
  });
  await run('fewer than four references do not call the backend or reuse an old result', async () => {
    let requests = 0; const validator = new CalibrationValidator(async () => { requests += 1; return diagnostics; });
    await validator.validate([camera], scope, () => {});
    const fewer = { ...camera, pairs: camera.pairs.slice(0,3) };
    const checks = await validator.validate([fewer], scope, () => {});
    assert.deepEqual(checks, {});
    assert.equal(requests, 1);
    assert.match(calibrationMessage(fewer), /3 referencias colocadas · faltan/);
  });
  await run('editing references immediately invalidates the previous result', async () => {
    const checks = await new CalibrationValidator(async () => diagnostics).validate([camera], scope, () => {});
    const edited = { ...camera, pairs: camera.pairs.map(pair => [...pair]) }; edited.pairs[0][2] = .5;
    assert.equal(currentCalibration(edited, scope, checks), undefined);
    assert.equal(geometry(ready(checks, { ...config, cameras:[edited] })).done, false);
  });
  await run('project, server, plan and camera identity cannot inherit another result', async () => {
    const checks = await new CalibrationValidator(async () => diagnostics).validate([camera], scope, () => {});
    for (const context of [{...scope,projectId:'other'}, {...scope,serverInstance:'restarted'}]) {
      assert.equal(currentCalibration(camera, context, checks), undefined);
      assert.equal(geometry(ready(checks, config, context)).done, false);
    }
    assert.equal(currentCalibration({...camera,planId:'other'},scope,checks), undefined);
    assert.equal(currentCalibration({...camera,id:'B'},scope,checks), undefined);
  });
  await run('late success cannot replace a newer failed validation', async () => {
    const first = deferred(), second = deferred(); let calls = 0, published;
    const validator = new CalibrationValidator(() => (++calls === 1 ? first : second).promise);
    const old = validator.validate([camera], scope, value => { published = value; });
    const changed = {...camera,pairs:[...camera.pairs,[.5,.5,6,4]]};
    const fresh = validator.validate([changed], scope, value => { published = value; });
    assert.equal(published.A.status,'checking');
    second.reject(new ApiError(crossed,400)); await fresh;
    first.resolve(diagnostics); assert.equal(await old,undefined);
    assert.equal(published.A.status,'invalid');
    assert.equal(published.A.key,calibrationKey(changed,scope));
  });
  await run('a response from a previous project is discarded even with identical pairs', async () => {
    const first = deferred(), second = deferred(); let calls=0, published;
    const validator = new CalibrationValidator(() => (++calls === 1 ? first : second).promise);
    const old = validator.validate([camera],scope,value => { published=value; });
    const nextScope = {...scope,projectId:'other'};
    const fresh = validator.validate([camera],nextScope,value => { published=value; });
    second.resolve(diagnostics); await fresh;
    first.reject(new ApiError(crossed,400)); assert.equal(await old,undefined);
    assert.equal(published.A.key,calibrationKey(camera,nextScope));
    assert.equal(published.A.status,'valid');
  });
  await run('disconnect/unmount cancellation cannot publish a late result', async () => {
    const pending = deferred(); const updates=[];
    const validator = new CalibrationValidator(() => pending.promise);
    const operation = validator.validate([camera],scope,value => updates.push(value));
    validator.clear(); pending.resolve(diagnostics);
    assert.equal(await operation,undefined);
    assert.equal(updates.length,1);
    assert.equal(updates[0].A.status,'checking');
  });
  await run('matching results are reused and explicit validation can retry', async () => {
    let calls=0; const validator = new CalibrationValidator(async () => { calls += 1; return diagnostics; });
    await validator.validate([camera],scope,()=>{});
    await validator.validate([camera],scope,()=>{});
    assert.equal(calls,1);
    await validator.validate([camera],scope,()=>{},camera.id);
    assert.equal(calls,2);
  });
  await run('network/auth failures remain unverified instead of invalid geometry', async () => {
    for (const error of [new Error('Sin conexión'),new ApiError('Inicia sesión',401),new ApiError('Solo operador',403)]) {
      const checks = await new CalibrationValidator(async () => { throw error; }).validate([camera],scope,()=>{});
      assert.equal(checks.A.status,'unavailable');
      assert.equal(geometry(ready(checks)).done,false);
      assert.match(calibrationMessage(camera,checks.A),/sin comprobar/);
    }
  });
  await run('one valid camera cannot mask another invalid camera', async () => {
    const second={...camera,id:'B',pairs:[...camera.pairs,[.5,.5,6,4]]};
    const checks = await new CalibrationValidator(async pairs => { if(pairs.length>4)throw new ApiError(crossed,400); return diagnostics; }).validate([camera,second],scope,()=>{});
    assert.equal(checks.A.status,'valid'); assert.equal(checks.B.status,'invalid');
    assert.equal(geometry(ready(checks,{...config,cameras:[camera,second]})).done,false);
  });
  await run('failed save preserves dirty state, exposes cause and rejects the caller', async () => {
    const error = new ApiError(crossed,400); const events=[]; let dirty=true,saving=false,message='';
    await assert.rejects(saveWithFeedback(async () => { throw error; }, {
      started:()=>{saving=true;events.push('start');}, saved:()=>{dirty=false;events.push('saved');},
      failed:value=>{message=value;events.push('failed');},finished:()=>{saving=false;events.push('finished');},
    }), value => value === error);
    assert.deepEqual(events,['start','failed','finished']);
    assert.equal(dirty,true); assert.equal(saving,false); assert.equal(message,crossed);
    assert.equal(saveStatusLabel(message,saving,dirty),'No se pudo guardar');
  });
  await run('successful save only marks saved after response and then clears saving', async () => {
    const pending=deferred(); const events=[]; let dirty=true,saving=false;
    const operation=saveWithFeedback(()=>pending.promise,{
      started:()=>{saving=true;events.push('start');},saved:()=>{dirty=false;events.push('saved');},
      failed:()=>assert.fail('unexpected failure'),finished:()=>{saving=false;events.push('finished');},
    });
    assert.equal(dirty,true); assert.equal(saveStatusLabel('',saving,dirty),'Guardando…');
    pending.resolve({ok:true}); await operation;
    assert.deepEqual(events,['start','saved','finished']);
    assert.equal(saveStatusLabel('',saving,dirty),'Guardado');
    assert.equal(saveStatusLabel('',false,true),'Cambios sin guardar');
  });
  await run('queued saves cannot overtake the earlier backend write and final saved state matches the backend', async () => {
    const queue=new ConfigSaveQueue(), gates={A:deferred(),B:deferred()}, requests=[];
    let backend=null,saved=null,sequence=0,pending=0;
    const submit=name=>{
      const own=++sequence;
      return saveWithFeedback(()=>queue.enqueue({name},()=>true,async snapshot=>{
        requests.push(snapshot.name);
        await gates[snapshot.name].promise;
        backend=snapshot.name;
        return {ok:true};
      }),{
        started:()=>{pending+=1;},saved:()=>{if(own===sequence)saved=name;},
        failed:()=>assert.fail('unexpected failure'),finished:()=>{pending-=1;},
      });
    };
    const first=submit('A'), second=submit('B');
    await Promise.resolve();
    assert.deepEqual(requests,['A']); assert.equal(pending,2); assert.equal(saved,null);
    gates.A.resolve(); await first;
    assert.equal(backend,'A'); assert.deepEqual(requests,['A','B']); assert.equal(saved,null);
    gates.B.resolve(); await second;
    assert.equal(backend,'B'); assert.equal(saved,backend); assert.equal(pending,0);
  });
  await run('a rejected first save does not poison the next queued save', async () => {
    const queue=new ConfigSaveQueue(), gate=deferred(), requests=[];
    const first=queue.enqueue({name:'A'},()=>true,async snapshot=>{requests.push(snapshot.name);await gate.promise;});
    const rejected=assert.rejects(first,error=>error.message==='invalid A');
    const second=queue.enqueue({name:'B'},()=>true,async snapshot=>{requests.push(snapshot.name);});
    await Promise.resolve(); assert.deepEqual(requests,['A']);
    gate.reject(new ApiError('invalid A',400)); await rejected; await second;
    assert.deepEqual(requests,['A','B']);
  });
  await run('the queued request uses its captured payload even if the caller mutates the draft', async () => {
    const queue=new ConfigSaveQueue(), gate=deferred(); let submitted;
    const first=queue.enqueue({},()=>true,()=>gate.promise);
    const draft={camera:{pairs:[[0,0,0,0]]}};
    const second=queue.enqueue(draft,()=>true,async snapshot=>{submitted=snapshot;});
    draft.camera.pairs[0][2]=999;
    gate.resolve(); await first; await second;
    assert.equal(submitted.camera.pairs[0][2],0); assert.notEqual(submitted,draft);
  });
  await run('a queued draft whose project changed is cancelled before its write and the new project can save', async () => {
    const queue=new ConfigSaveQueue(), gate=deferred(), requests=[]; let owner='old',generation=0;
    const first=queue.enqueue({name:'first'},()=>true,async snapshot=>{requests.push(snapshot.name);await gate.promise;});
    const epoch=generation;
    const cancelled=queue.enqueue({name:'stale'},()=>owner==='old'&&generation===epoch,async snapshot=>{requests.push(snapshot.name);});
    const rejected=assert.rejects(cancelled,/proyecto cambió/);
    await Promise.resolve(); owner='new';generation+=1;
    const fresh=queue.enqueue({name:'new-project'},()=>owner==='new',async snapshot=>{requests.push(snapshot.name);});
    gate.resolve(); await first; await rejected; await fresh;
    assert.deepEqual(requests,['first','new-project']);
    // Returning to the same ID still cannot revive the previous ownership.
    owner='old'; assert.equal(owner==='old'&&generation===epoch,false);
  });
  console.log(`PASS ${passed} calibration/readiness/save checks; no network, camera or persistent fixtures.`);
} finally {
  const safeRoot=resolve(tmpdir()) + sep;
  if (!resolve(temporary).startsWith(safeRoot) || !basename(temporary).startsWith('aerotrack-calibration-')) throw Error('Unexpected temporary directory');
  rmSync(temporary,{recursive:true,force:true});
}
