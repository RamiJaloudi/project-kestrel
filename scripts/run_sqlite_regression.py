"""Run all collected tests in isolated file shards, retaining every log/temp tree.

No extra pytest plugin is required. This runner never uses PostgreSQL fixtures.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/'backend'


def source_hashes():
    paths=[*(BACKEND/'kestrel').rglob('*.py'),*(BACKEND/'tests').rglob('*.py'),*(ROOT/'scripts').glob('*.py'),BACKEND/'pyproject.toml']
    paths.extend(path for path in (ROOT/'frontend'/'src').rglob('*') if path.is_file() and path.suffix in {'.ts','.tsx','.css'})
    return {str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(set(paths))}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--shards',type=int,choices=range(1,5),default=4)
    parser.add_argument('--plan-only',action='store_true')
    options=parser.parse_args()
    directory=ROOT/'.runtime'/'test-runs'/('datatables-'+uuid.uuid4().hex)
    directory.mkdir(parents=True,exist_ok=False)
    environment={**os.environ,'KESTREL_TEST_POSTGRES':'0','PYTHONUNBUFFERED':'1','PYTHONUTF8':'1'}
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    command=[sys.executable,'-u','-X','utf8','-m','pytest']
    collected=subprocess.run([*command,'--collect-only','-q'],cwd=BACKEND,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=flags)
    (directory/'collection.log').write_bytes(collected.stdout)
    if collected.returncode:raise RuntimeError('Test collection failed; inspect the retained collection.log')
    nodes=[line for line in collected.stdout.decode('utf8',errors='replace').splitlines() if line.startswith('tests/') and '::' in line]
    if not nodes or len(nodes)!=len(set(nodes)):raise RuntimeError('Expected a nonempty unique test collection')
    counts=Counter(node.split('::',1)[0] for node in nodes)
    buckets=[{'files':[],'expected':0} for _ in range(options.shards)]
    for file,count in sorted(counts.items(),key=lambda item:(-item[1],item[0])):
        bucket=min(buckets,key=lambda item:item['expected']);bucket['files'].append(file);bucket['expected']+=count
    assert set(file for bucket in buckets for file in bucket['files'])==set(counts)
    plan={'collected':len(nodes),'files':len(counts),'sqlite_only':True,'shards':buckets}
    (directory/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
    print(json.dumps({'directory':str(directory),'collected':len(nodes),'planned_cases':[b['expected'] for b in buckets]}),flush=True)
    if options.plan_only:return
    frozen=source_hashes()
    (directory/'source-hashes.json').write_text(json.dumps(frozen,indent=2),encoding='utf8')
    started=time.monotonic();running=[]
    try:
        for index,bucket in enumerate(buckets,1):
            if not bucket['files']:continue
            output=(directory/f'shard-{index}.log').open('wb')
            process=subprocess.Popen([*command,'-q','--durations=5','--basetemp='+str(directory/f'tmp-{index}'),*bucket['files']],cwd=BACKEND,env=environment,stdout=output,stderr=subprocess.STDOUT,creationflags=flags)
            running.append((index,process,output))
        (directory/'processes.json').write_text(json.dumps([{'shard':i,'pid':p.pid} for i,p,_ in running],indent=2),encoding='utf8')
        while any(p.poll() is None for _,p,_ in running):
            print(json.dumps({'elapsed_seconds':round(time.monotonic()-started),'completed_shards':sum(p.poll() is not None for _,p,_ in running),'total_shards':len(running)}),flush=True)
            time.sleep(10)
    except BaseException:
        for _,process,_ in running:
            if process.poll() is None:
                if os.name=='nt':subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
                else:process.terminate()
        raise
    finally:
        for _,_,output in running:output.close()
    outcomes=[]
    for index,process,_ in running:
        log=(directory/f'shard-{index}.log').read_text(encoding='utf8',errors='replace')
        summaries=[line for line in log.splitlines() if re.search(r'\b\d+ (passed|failed|skipped|error|errors|xfailed|xpassed)\b',line) and re.search(r'\bin \d',line)]
        summary=summaries[-1] if summaries else ''
        results={kind:int(number) for number,kind in re.findall(r'(\d+) (passed|failed|skipped|errors?|xfailed|xpassed)\b',summary)}
        executed=sum(results.get(key,0) for key in ['passed','failed','skipped','xfailed','xpassed'])
        outcomes.append({'shard':index,'exit_code':process.returncode,'expected':buckets[index-1]['expected'],'executed':executed,'results':results,'summary':summary})
    after=source_hashes()
    changed=sorted(path for path in set(frozen)|set(after) if frozen.get(path)!=after.get(path))
    verified=not changed and all(o['exit_code']==0 and o['expected']==o['executed'] for o in outcomes)
    report={'verified':verified,'collected':len(nodes),'elapsed_seconds':round(time.monotonic()-started,2),'source_unchanged':not changed,'changed_source_files':changed,'shards':outcomes}
    (directory/'result.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report),flush=True)
    if not verified:raise SystemExit(1)


if __name__=='__main__':main()
