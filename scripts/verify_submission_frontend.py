"""Clean-extract a retained review ZIP and rebuild its frontend without downloads.

Uses an explicitly supplied existing node_modules copy. This verifies packaged
source completeness, not dependency installation from the Internet or deployment.
Every extracted/build file and log is retained under a new isolated runtime path.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
from uuid import uuid4
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
BUILD='tsc -b && vite build && node scripts/copy-swagger.mjs'


def sha(data):return hashlib.sha256(data).hexdigest()


def verify(archive_path,dependencies):
    archive_path=Path(archive_path).resolve(strict=True)
    dependencies=Path(dependencies).resolve(strict=True)
    if not archive_path.is_relative_to(ROOT/'delivery/submission_bundles') or archive_path.name!='Project_Kestrel_review_source.zip':
        raise ValueError('Expected a retained local submission source ZIP')
    if dependencies.name!='node_modules' or not dependencies.is_dir():raise ValueError('Explicit existing dependency directory required')
    # No external links/reparse points are followed into a private tree.
    for path in [dependencies,*dependencies.rglob('*')]:
        if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):
            raise ValueError('Dependency copy must contain no symbolic links or reparse points')
    directory=ROOT/'.runtime/submission-build-checks'/uuid4().hex
    directory.mkdir(parents=True,exist_ok=False)
    frontend=directory/'frontend'
    frontend.mkdir()
    with ZipFile(archive_path) as archive:
        names=archive.namelist()
        if (len(names)!=len(set(names)) or len(names)>10000
            or sum(item.file_size for item in archive.infolist())>256*1024*1024
            or any(item.file_size>32*1024*1024 for item in archive.infolist())):raise ValueError('Invalid or oversized ZIP members')
        if archive.testzip() is not None:raise ValueError('ZIP CRC failure')
        manifest=json.loads(archive.read('SUBMISSION_MANIFEST.json'))
        entries=manifest['files']
        if set(names)!={entry['path'] for entry in entries}|{'SUBMISSION_MANIFEST.json'}:raise ValueError('ZIP members differ from manifest')
        extracted=[]
        for entry in entries:
            name=entry['path'];relative=PurePosixPath(name)
            if '\\' in name or relative.is_absolute() or '..' in relative.parts or ':' in name:raise ValueError('Unsafe ZIP path')
            data=archive.read(name)
            if sha(data)!=entry['sha256'] or len(data)!=entry['bytes']:raise ValueError('Packaged source checksum mismatch')
            if relative.parts[0]!='frontend':continue
            if any(part in {'node_modules','dist','.runtime','.env'} for part in relative.parts):raise ValueError('Unexpected frontend runtime/dependency member')
            target=directory.joinpath(*relative.parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:stream.write(data)
            extracted.append(name)
    package=json.loads((frontend/'package.json').read_text())
    if package['scripts']['build']!=BUILD:raise ValueError('Review the changed build command before executing it')
    seed_lock=dependencies.parent/'package-lock.json'
    if not seed_lock.is_file() or sha(seed_lock.read_bytes())!=sha((frontend/'package-lock.json').read_bytes()):
        raise ValueError('Existing dependency copy must have the same package lock')
    shutil.copytree(dependencies,frontend/'node_modules',symlinks=False)
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if not npm:raise RuntimeError('Existing npm runtime required; nothing is installed')
    environment={**os.environ,'npm_config_offline':'true','npm_config_audit':'false','npm_config_fund':'false'}
    result=subprocess.run([npm,'run','build'],cwd=frontend,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    (directory/'frontend-build.log').write_bytes(result.stdout)
    required=[frontend/'dist/index.html',frontend/'dist/swagger/swagger-ui-bundle.js',frontend/'dist/swagger/swagger-ui.css']
    verified=result.returncode==0 and all(path.is_file() and path.stat().st_size for path in required)
    receipt={'schema':'kestrel-clean-source-zip-frontend-build-1','archive_sha256':sha(archive_path.read_bytes()),
        'archive':str(archive_path.relative_to(ROOT)) if archive_path.is_relative_to(ROOT) else archive_path.name,
        'verified':verified,'frontend_members':len(extracted),'build_exit_code':result.returncode,
        'clean_source_extraction':True,'dependencies':'existing copy with matching package lock',
        'network_install_performed':False,'npm_offline':True,'operational_acceptance':False,
        'retained_directory':str(directory.relative_to(ROOT)),
        'outputs':[{'path':str(path.relative_to(directory)),'sha256':sha(path.read_bytes())} for path in required if path.is_file()]}
    (directory/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if not verified:raise RuntimeError('Clean source ZIP frontend build failed; inspect retained log: '+str(directory))
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--dependencies',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(verify(args.archive,args.dependencies),indent=2))


if __name__=='__main__':main()
