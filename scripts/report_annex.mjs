// Compatibility CLI only. The application invokes the Python worker directly.
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
let input='';for await(const chunk of process.stdin){input+=chunk;if(input.length>2097152)throw new Error('Report request exceeded bounds');}
const payload=JSON.parse(input);payload.format='xlsx';
const python=process.env.KESTREL_REPORT_PYTHON||path.join(root,'backend','.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const result=spawnSync(python,[path.join(root,'scripts/report_artifacts.py')],{input:JSON.stringify(payload),timeout:45000,maxBuffer:20971520,windowsHide:true});
if(result.status!==0||!result.stdout?.subarray(0,2).equals(Buffer.from('PK')))throw new Error('Portable report renderer unavailable');
await fs.writeFile(process.argv[2],result.stdout);
