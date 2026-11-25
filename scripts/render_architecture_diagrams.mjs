// PNG exports from the canonical vector diagrams. Sharp is an authoring dependency.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const options=process.env.KESTREL_ARTIFACT_MODULES?{paths:[process.env.KESTREL_ARTIFACT_MODULES]}:undefined;
const sharp=require(require.resolve('sharp',options));
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const catalogue=JSON.parse(await fs.readFile(path.join(root,'diagrams/catalog.json'),'utf8'));
for(const diagram of catalogue.diagrams){
 const base=path.join(root,'diagrams',diagram.folder,diagram.id);
 await sharp(await fs.readFile(base+'.svg')).png().toFile(base+'.png');
}
console.log(JSON.stringify({pngs:catalogue.diagrams.length}));
