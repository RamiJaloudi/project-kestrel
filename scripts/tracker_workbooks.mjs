// Compatibility CLI only; no bundled proprietary workbook library is required.
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
let input='';for await(const chunk of process.stdin){input+=chunk;if(input.length>2097152)throw new Error('Workbook request exceeded bounds');}
const python=process.env.KESTREL_REPORT_PYTHON||path.join(root,'backend','.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const result=spawnSync(python,[path.join(root,'scripts/portable_workbooks.py'),...(process.argv.includes('--preview')?['--preview']:[])],{input,timeout:45000,maxBuffer:3145728,windowsHide:true});
if(result.status!==0||!result.stdout?.subarray(0,2).equals(Buffer.from('PK')))throw new Error('Portable workbook renderer unavailable');
process.stdout.write('\nKESTREL_XLSX_V1\n'+result.stdout.toString('base64'));
