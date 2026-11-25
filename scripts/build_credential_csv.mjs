// Explicit local export. Never prints password values or copies DB credentials.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
const root=path.resolve(import.meta.dirname,'..');
const require=createRequire(path.join(root,'.runtime/credential-export-builder/builder.mjs'));
const {Workbook}=require('@oai/artifact-tool');
const rows=JSON.parse(await fs.readFile(path.join(root,'.runtime/credential-export.json'),'utf8'));
const headers=['DisplayName','Employer','UPN','Email','Password','Roles','PortalURL','Active'];
if(rows.length!==36||new Set(rows.map(r=>r.UPN)).size!==36)throw new Error('Credential row count/uniqueness failed');
const matrix=[headers,...rows.map(row=>headers.map(h=>row[h]))];
if(matrix.some(row=>row.some(v=>typeof v!=='string'||/^[=+\-@\t\r\n]/.test(v))))throw new Error('CSV literal-field validation failed');
const workbook=Workbook.create();
const sheet=workbook.worksheets.add('Credentials');
const range=sheet.getRange(`A1:H${matrix.length}`);
range.setNumberFormat('@');range.values=matrix;
workbook.recalculate();
const values=range.values;
if(JSON.stringify(values)!==JSON.stringify(matrix))throw new Error('Spreadsheet value verification failed');
const outputDir=path.join(root,'outputs/01a1f43e-5e06-7fa1-8f57-592009775d46');
await fs.mkdir(outputDir,{recursive:true});
const output=path.join(outputDir,'Kestrel_Demo_Credentials.csv');
// CSV requested: plain rectangular data, UTF-8 BOM and CRLF for Windows Excel.
const csv=values.map(row=>row.map(value=>'"'+value.replaceAll('"','""')+'"').join(',')).join('\r\n')+'\r\n';
await fs.writeFile(output,'\uFEFF'+csv,'utf8');
console.log('CSV saved: 36 verified account rows, 8 columns, fictional employer domains.');
