import path from 'node:path';
import {createRequire} from 'node:module';
const root=path.resolve(import.meta.dirname,'..');
if(!process.env.KESTREL_OCR_NODE_MODULES)throw new Error('Configure the OCR package directory');
const require=createRequire(path.join(process.env.KESTREL_OCR_NODE_MODULES,'../ocr-loader.mjs'));
const {createWorker}=require('tesseract.js');
const worker=await createWorker(['eng','deu'],1,{langPath:process.env.KESTREL_OCR_MODELS||path.join(root,'.runtime/ocr-models'),gzip:false,cacheMethod:'none',logger:()=>{},errorHandler:()=>{}});
try{const {data}=await worker.recognize(process.argv[2],{}, {text:true,tsv:true});process.stdout.write(JSON.stringify({tsv:data.tsv,confidence:data.confidence,engine:'tesseract.js-7.0.0;eng+deu'}));}
finally{await worker.terminate();}
