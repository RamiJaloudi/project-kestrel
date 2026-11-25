import csv,io,json,hashlib,os,subprocess,tempfile
from pathlib import Path
from fastapi import HTTPException
from kestrel.adapters.extraction import digest,canonical,MAX_TEXT
from kestrel.adapters import runtime
ROOT=runtime.ROOT
MODEL_COMMIT='87416418657359cb625c412a48b6e1d6d41c29bd'
MODEL_HASHES={'eng':'7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2','deu':'19d219bbb6672c869d20a9636c6816a81eb9a71796cb93ebe0cb1530e2cdb22d'}

def components():
    renderer=runtime.executable('pdftoppm','pdftoppm')
    engine=runtime.option('ocr_engine','auto')
    if engine not in {'auto','native','tesseract-js'}:raise ValueError('Unsupported OCR engine')
    if engine!='tesseract-js':
        try:return renderer,'native',runtime.executable('tesseract','tesseract'),None
        except OSError:
            if engine=='native':raise
    node,modules=runtime.legacy_ocr_node()
    return renderer,'tesseract-js',node,modules

def verify_models():
    folder=runtime.ocr_models()
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8-sig'))
    if not isinstance(manifest,dict) or not isinstance(manifest.get('models'),dict):raise ValueError('Invalid OCR model manifest')
    if manifest.get('commit')!=MODEL_COMMIT or set(manifest.get('models',{}))!=set(MODEL_HASHES):raise ValueError('Unsupported OCR model manifest')
    for lang,expected in MODEL_HASHES.items():
        model=folder/f'{lang}.traineddata'
        if not isinstance(manifest['models'][lang],dict) or manifest['models'][lang].get('sha256')!=expected or model.stat().st_size>10*1024*1024 or hashlib.sha256(model.read_bytes()).hexdigest()!=expected:raise ValueError('OCR model integrity failure')
    return folder
def available():
    try:components();verify_models();return True
    except (OSError,ValueError,KeyError,TypeError):return False
def tsv_unit(tsv,number):
    words=[];text='';last=None
    columns=['level','page_num','block_num','par_num','line_num','word_num','left','top','width','height','conf','text']
    for row in csv.DictReader(io.StringIO(tsv),delimiter='\t',fieldnames=None if tsv.startswith('level\t') else columns):
        word=(row.get('text') or '').strip()
        if row.get('level')!='5' or not word:continue
        line=tuple(row[k] for k in ['block_num','par_num','line_num'])
        if text:text+='\n' if last!=line else ' '
        start=len(text);text+=word
        words.append({'start':start,'end':len(text),'text':word,'left':int(row['left']),'top':int(row['top']),'width':int(row['width']),'height':int(row['height']),'confidence':float(row['conf'])});last=line
    if not words:raise HTTPException(422,'No OCR text detected; source remains unprocessed')
    return {'number':number,'locator':f'Page {number}','text':text,'ocr':True,'words':words}
def extract_pdf(data,heartbeat=None):
    from pypdf import PdfReader
    if not data or len(data)>3*1024*1024 or not data.startswith(b'%PDF-'):raise HTTPException(422,'A bounded PDF source is required')
    try:renderer,engine,recognizer,modules=components();models=verify_models()
    except (OSError,ValueError,KeyError,TypeError):raise HTTPException(503,'English/German OCR runtime or verified models are unavailable') from None
    try:
        reader=PdfReader(io.BytesIO(data),strict=True)
        if reader.is_encrypted:raise ValueError()
        count=len(reader.pages)
    except Exception:raise HTTPException(422,'PDF could not be safely read for OCR') from None
    if count>10:raise HTTPException(413,'Local OCR supports at most 10 pages per document')
    directory=ROOT/'.runtime/ocr-work';directory.mkdir(exist_ok=True,parents=True);units=[]
    with tempfile.TemporaryDirectory(dir=directory) as folder:
        source=Path(folder)/'source.pdf';source.write_bytes(data)
        def run(command,timeout,env=None):
            try:
                return runtime.run_bytes(command,timeout=timeout,limit=4*1024*1024,env=env)
            except (OSError,subprocess.TimeoutExpired):raise HTTPException(503,'OCR component unavailable, failed or timed out') from None
        if engine=='native':
            version=run([recognizer,'--version'],5).decode('utf-8',errors='replace').splitlines()[0]
            if not version.startswith('tesseract 5.'):raise HTTPException(503,'Configure a verified Tesseract 5 runtime')
            extractor='ocr:'+version[:80]+';eng+deu;'+MODEL_COMMIT[:12]
        else:
            config=json.loads((modules/'tesseract.js/package.json').read_text(encoding='utf-8'))
            if config.get('version')!='7.0.0':raise HTTPException(503,'Configure the verified Tesseract.js 7.0.0 runtime')
            extractor='ocr:tesseract.js-7.0.0;'+MODEL_COMMIT[:12]
        for index in range(1,count+1):
            if heartbeat:heartbeat()
            page=Path(folder)/'page'
            run([renderer,'-f',index,'-l',index,'-r',150,'-scale-to',2200,'-singlefile','-png',source,page],15)
            image=Path(str(page)+'.png')
            if not image.is_file() or image.stat().st_size>20*1024*1024:raise HTTPException(503,'OCR raster exceeded bounds')
            if engine=='native':
                env={**os.environ,'OMP_THREAD_LIMIT':'1'}
                tsv=run([recognizer,image,'stdout','--tessdata-dir',models,'-l','eng+deu','--oem','1','tsv'],25,env).decode('utf-8')
                result={'tsv':tsv}
            else:
                env={**os.environ,'KESTREL_OCR_MODELS':str(models),'KESTREL_OCR_NODE_MODULES':str(modules)}
                result=json.loads(run([recognizer,ROOT/'scripts/ocr_page.mjs',image],25,env))
            unit=tsv_unit(result['tsv'],index)
            import struct
            width,height=struct.unpack('>II',Path(str(page)+'.png').read_bytes()[16:24])
            confidence=result.get('confidence',sum(w['confidence'] for w in unit['words'])/len(unit['words']))
            unit.update(image_width=width,image_height=height,coordinate_space='raster pixels; origin top-left',pdf_width_points=float(reader.pages[index-1].mediabox.width),pdf_height_points=float(reader.pages[index-1].mediabox.height),rotation=int(reader.pages[index-1].get('/Rotate',0)),ocr_confidence=confidence)
            units.append(unit)
            if heartbeat:heartbeat()
            if sum(len(u['text']) for u in units)>MAX_TEXT:raise HTTPException(413,'OCR text exceeds extraction limits')
    return {'units':units,'media_type':'application/pdf','extractor':extractor,
        'status':'ready','bytes_hash':digest(data),'text_hash':digest(canonical(units).encode())}
