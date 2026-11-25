import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
const root=path.resolve(import.meta.dirname,'..');
const require=createRequire(path.join(root,'.runtime/synthetic-build/builder.mjs'));
const {Workbook,SpreadsheetFile}=require('@oai/artifact-tool');
for(const wave of [1,2]){
 const output=path.join(root,'../Synthetic_Data',`Wave_${wave}`,`P001_v${wave}_clean_team_pricing.xlsx`);
 try{await fs.access(output);if(!process.argv.includes('--rebuild')){console.log(`Wave ${wave} pricing already exists; preserved.`);continue;}}catch{}
 const wb=Workbook.create(),sheet=wb.worksheets.add('Pricing');
 sheet.getRange('A1:C7').values=[
  [`Synthetic clean-team pricing wave ${wave}`,'',''],['Customer','Monthly fee EUR','Restriction'],
  ['Orion Demo AG',wave===1?120000:118000,'exclusive pricing - clean-team'],
  ['Larch Synthetic GmbH',wave===1?85000:90000,'Consent before change of control'],
  ['Fable Test Ltd',64000,'Synthetic amounts only'],['Handling','Named pricing scope','No external source access'],
  ['Matter','012345-789012','Version '+wave]
 ];
 sheet.showGridLines=false;sheet.getRange('A1:C7').format.font={name:'Arial',size:11};
 sheet.getRange('A1').format.font={name:'Arial',size:14,bold:true};
 sheet.getRange('A2:C2').format={fill:'#203c5b',font:{name:'Arial',size:11,color:'#ffffff',bold:true}};
 sheet.getRange('A1:A7').format.columnWidth=34;sheet.getRange('B1:B7').format.columnWidth=24;sheet.getRange('C1:C7').format.columnWidth=42;
 sheet.getRange('A1:C7').format.rowHeight=25;sheet.getRange('B3:B5').setNumberFormat('#,##0"   "');sheet.freezePanes.freezeRows(2);
 wb.recalculate();
 const result=await SpreadsheetFile.exportXlsx(wb);await result.save(output);
 try{await fs.rename(output+'.inspect.ndjson',path.join(root,'.runtime/fixture-qa',`pricing-wave-${wave}.inspect.ndjson`));}catch(error){if(error.code!=='ENOENT')throw error;}
 const png=await wb.render({sheetName:'Pricing',range:'A1:C7',scale:1.5,format:'png'});
 await fs.writeFile(path.join(root,'.runtime/fixture-qa',`pricing-wave-${wave}.png`),new Uint8Array(await png.arrayBuffer()));
 console.log(`Wave ${wave} synthetic pricing workbook saved and rendered.`);
}
