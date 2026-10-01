// Existing Vite/React only. Serve the emitted directory on an isolated loopback
// HTTP server and open it in a browser; body[data-result] is PASS or FAIL.
import { build } from 'vite';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
const scripts=dirname(fileURLToPath(import.meta.url));
const root=resolve(scripts,'..');
if(!process.argv[2])throw Error('Specify a NEW external evidence output directory');
const out=resolve(process.argv[2]);
if(!relative(resolve(root,'../..'),out).startsWith('..'))throw Error('Output must be outside the repository');
mkdirSync(out,{recursive:false});
await build({root,configFile:false,define:{'process.env.NODE_ENV':'"development"'},esbuild:{jsx:'automatic'},build:{outDir:out,emptyOutDir:false,target:'es2022',
  lib:{entry:resolve(scripts,'audit-browser-regression.tsx'),formats:['es'],fileName:()=> 'regression.js'}}});
writeFileSync(resolve(out,'index.html'),'<!doctype html><html><head><meta charset="UTF-8"><title>AUD-05 running</title></head><body><h1>Real React caller regression — synthetic HTTP</h1><pre id="results">RUNNING</pre><div id="root"></div><script type="module" src="./regression.js"></script></body></html>');
