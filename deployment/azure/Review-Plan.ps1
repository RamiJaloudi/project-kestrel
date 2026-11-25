# Offline review only. This file contains no Azure login, deployment or DNS call.
[CmdletBinding()]
param(
 [string]$ParametersPath = '',
 [string]$CompilerPath = '',
 [string]$OutputPath = '',
 [string]$PriceReceiptPath = '',
 [switch]$PackageCode
)
$ErrorActionPreference='Stop'
$reviewStage='paths'
function Get-PlanHash([string]$LiteralPath) {
 $stream=[System.IO.File]::OpenRead([System.IO.Path]::GetFullPath($LiteralPath))
 $algorithm=[System.Security.Cryptography.SHA256]::Create()
 try {return ([System.BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToUpperInvariant()}
 finally {$algorithm.Dispose();$stream.Dispose()}
}
function New-CodeOnlyReviewPackage([string]$WorkspaceRoot) {
 # Uses only the application's published release-hash allowlist. No environment,
 # live database, archive, key, owner approval or credential is read or exported.
 $python=Join-Path $WorkspaceRoot 'backend\.venv\Scripts\python.exe'
 if(!(Test-Path -LiteralPath $python -PathType Leaf)){throw 'Reviewed local Python is required for code packaging.'}
 $helper=@'
import ast,hashlib,inspect,json,stat,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
root=Path(sys.argv[1]).resolve(strict=True)
sys.path.insert(0,str(root/'backend'))
from kestrel.deployment_settings import release_hash
tree=ast.parse(inspect.getsource(release_hash))
assign=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='patterns' for t in n.targets))
patterns=ast.literal_eval(assign.value)
if not patterns or any(not isinstance(p,str) for p in patterns):raise RuntimeError('Release allowlist unavailable')
paths=sorted({p for pattern in patterns for p in root.glob(pattern) if p.is_file() and '__pycache__' not in p.parts})
allowed_deployment={'deployment/Caddyfile.public.example','deployment/azure/README.md','deployment/azure/main.bicep','deployment/azure/main.json','deployment/azure/parameters.example.json','deployment/azure/Review-Plan.ps1'}
for path in paths:
    relative=path.relative_to(root).as_posix()
    if path.name=='.env' or path.suffix.lower() in {'.dpapi','.dump','.backup','.db','.sqlite','.sqlite3','.pem','.key','.pfx','.log'}:raise RuntimeError('Credential/runtime file type refused')
    if relative.startswith('deployment/') and relative not in allowed_deployment:raise RuntimeError('Unreviewed deployment file refused')
    for item in [path,*path.parents]:
        if item==root:break
        if item.is_symlink() or getattr(item.lstat(),'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0):raise RuntimeError('Reparse point refused')
    if not path.resolve(strict=True).is_relative_to(root):raise RuntimeError('Release path outside workspace')
    if path.stat().st_size>32*1024*1024:raise RuntimeError('Individual code asset exceeds package bound')
if sum(p.stat().st_size for p in paths)>200*1024*1024:raise RuntimeError('Code package exceeds bound')
before=release_hash()
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
directory=root/'.runtime/azure/packages';directory.mkdir(parents=True,exist_ok=True)
archive=directory/('kestrel-code-'+stamp+'-'+before[:12]+'.zip')
rows=[]
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as output:
    for path in paths:
        data=path.read_bytes();name=path.relative_to(root).as_posix()
        rows.append({'path':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        output.writestr(name,data)
    output.writestr('CODE_PACKAGE_MANIFEST.json',json.dumps({'schema':'kestrel-code-package-1','release_hash':before,'files':rows,'scope':'Release code/assets only; runtime data and credential file types excluded; final synthetic/secret review still required'},sort_keys=True,indent=2))
if release_hash()!=before:raise RuntimeError('Release changed during packaging; package is not approved')
with zipfile.ZipFile(archive) as check:
    if check.testzip() is not None:raise RuntimeError('ZIP integrity check failed')
receipt={'schema':'kestrel-code-package-review-1','created_at_utc':datetime.now(timezone.utc).isoformat(),'archive':str(archive),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'release_hash':before,'file_count':len(rows),'runtime_data_included':False,'owner_approval_created':False,'cloud_transfer_performed':False}
manifest=archive.with_suffix('.receipt.json');manifest.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
'@
 $raw=$helper | & $python - $WorkspaceRoot 2>&1
 if($LASTEXITCODE -ne 0){throw 'Code-only package review failed; no data transfer occurred.'}
 return (($raw -join [Environment]::NewLine) | ConvertFrom-Json)
}
try {
 $planRoot=$PSScriptRoot
 if(!$planRoot){$planRoot=Split-Path -Parent $MyInvocation.MyCommand.Path}
 if(!$ParametersPath){$ParametersPath=Join-Path $planRoot 'parameters.example.json'}
 if(!$CompilerPath){$CompilerPath=Join-Path $planRoot '..\..\.runtime\tools\bicep-0.49.2.exe'}
 if(!$OutputPath){$OutputPath=Join-Path $planRoot '..\..\.runtime\azure\closed-plan.json'}
 $reviewStage='compiler-integrity'
 $expectedCompiler='ACFFF0453C9BCF442AA97103ACBCD845EF366634E6EA2A2BA5734514409CE9C3'
 if (!(Test-Path -LiteralPath $CompilerPath -PathType Leaf)) {throw 'Pinned compiler missing. See README; no automatic download occurs.'}
 if ((Get-PlanHash $CompilerPath) -cne $expectedCompiler) {throw 'Compiler hash differs from the reviewed official release.'}
 $reviewStage='nonsecret-parameters'
 $parameters=Get-Content -LiteralPath $ParametersPath -Raw | ConvertFrom-Json
 $allowed=@('location','vmSize','vmName','adminUsername','adminSourceIp','allowPublicWeb')
 foreach($property in $parameters.parameters.PSObject.Properties){if($allowed -notcontains $property.Name){throw 'Only the six nonsecret review parameters are permitted. Do not put passwords in this file.'}}
 foreach($name in $allowed){if($null -eq $parameters.parameters.PSObject.Properties[$name]){throw 'All six nonsecret review parameters must be explicit.'}}
 if ($parameters.parameters.allowPublicWeb.value -isnot [bool] -or $parameters.parameters.allowPublicWeb.value) {throw 'This offline plan requires allowPublicWeb=false.'}
 if ($parameters.parameters.vmSize.value -cne 'Standard_B2as_v2') {throw 'VM size differs from the reviewed cost/design.'}
 if ($parameters.parameters.location.value -cne 'eastus2') {throw 'Region differs from the proposed cost/design; obtain a new quote first.'}
 if ($parameters.parameters.vmName.value -cnotmatch '^[a-z][a-z0-9-]{2,11}$') {throw 'Use a simple 3-12 character lowercase VM name.'}
 if ($parameters.parameters.adminUsername.value -cnotmatch '^[A-Za-z][A-Za-z0-9_-]{2,19}$') {throw 'Use a simple owner account name; no credential material.'}
 $ownerIp=[string]$parameters.parameters.adminSourceIp.value
 if ($ownerIp) {
  $parsedIp=$null
  if (![System.Net.IPAddress]::TryParse($ownerIp,[ref]$parsedIp) -or $parsedIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or $parsedIp.ToString() -cne $ownerIp -or $ownerIp -eq '0.0.0.0') {throw 'Owner administration address must be a single canonical IPv4 address; no CIDR or wildcard.'}
 }
 $reviewStage='output-directory'
 $folder=Split-Path -Parent ([System.IO.Path]::GetFullPath($OutputPath))
 New-Item -ItemType Directory -Force -Path $folder | Out-Null
 $compiled=Join-Path $folder 'reviewed-arm.json'
 $reviewStage='offline-compilation'
 & $CompilerPath build (Join-Path $planRoot 'main.bicep') --outfile $compiled
 if($LASTEXITCODE -ne 0){throw 'Bicep compilation failed.'}
 $reviewStage='compiled-declarations'
 $template=Get-Content -LiteralPath $compiled -Raw | ConvertFrom-Json
 if($template.parameters.adminPassword.type -cne 'securestring' -or $template.parameters.allowPublicWeb.defaultValue -ne $false){throw 'Compiled credential or ingress declarations differ.'}
 $networks=@($template.resources | Where-Object {$_.type -ceq 'Microsoft.Network/virtualNetworks'})
 if($networks.Count -ne 1 -or $networks[0].properties.subnets[0].properties.defaultOutboundAccess -ne $false){throw 'Explicit private-subnet declaration required.'}
 $reviewStage='receipt'
 $workspace=[System.IO.Path]::GetFullPath((Join-Path $planRoot '..\..'))
 if(!$PriceReceiptPath){$PriceReceiptPath=Join-Path $workspace '.runtime\azure\retail-prices-2026-11-24-latest.json';if(!(Test-Path -LiteralPath $PriceReceiptPath -PathType Leaf)){$PriceReceiptPath=Join-Path $workspace 'docs\evidence\66_azure_retail_prices_2026-11-24.json'}}
 $prices=Get-Content -LiteralPath $PriceReceiptPath -Raw | ConvertFrom-Json
 if($prices.source -cne 'https://prices.azure.com/api/retail/prices' -or $prices.currency -cne 'USD' -or $prices.region -cne 'eastus2' -or $prices.hours -ne 730){throw 'Matching public retail receipt required; it is not a subscription quote.'}
 $compute=@($prices.items | Where-Object {$_.component -ceq 'Standard_B2as_v2' -and $_.product -match 'Windows' -and $_.unit -ceq '1 Hour'})
 $os=@($prices.items | Where-Object {$_.meter -ceq 'E10 LRS Disk'})
 $data=@($prices.items | Where-Object {$_.meter -ceq 'E6 LRS Disk'})
 $ip=@($prices.items | Where-Object {$_.meter -ceq 'Standard IPv4 Static Public IP'})
 if($compute.Count -ne 1 -or $os.Count -ne 1 -or $data.Count -ne 1 -or $ip.Count -ne 1){throw 'Unique reviewed price meters required.'}
 $base=[math]::Round(([decimal]$compute[0].rate*730+[decimal]$os[0].rate+[decimal]$data[0].rate+[decimal]$ip[0].rate*730),2)
 $result=[ordered]@{
  schema='kestrel-azure-offline-plan-1';generated_at_utc=[DateTime]::UtcNow.ToString('o');scope='Offline preparation only; no Azure validation or resource creation';
  compiler_sha256=$expectedCompiler.ToLowerInvariant();template_sha256=(Get-PlanHash $compiled).ToLowerInvariant();
  parameters_sha256=(Get-PlanHash $ParametersPath).ToLowerInvariant();
  region='eastus2';vm_size='Standard_B2as_v2';windows='2022-datacenter-g2';public_web_open=$false;rdp='No rule unless a single owner IPv4 was supplied; /32 only';
  database='Local PostgreSQL; no public database/API/pgAdmin ports';disk_layout='128GiB OS +64GiB persistent data; disks detached on VM deletion';
  hosts=@('portal.ramijaloudi.com','firm.portal.ramijaloudi.com','halden.portal.ramijaloudi.com','castlegate.portal.ramijaloudi.com','admin.portal.ramijaloudi.com');
  outbound='Private subnet; explicit NIC Standard public IPv4. No NAT Gateway or implicit default SNAT';
  cost=[ordered]@{currency='USD';hours=730;base_monthly=$base;target_monthly=100;price_queried_utc=([DateTimeOffset]::Parse([string]$prices.queried_utc).ToUniversalTime().ToString('o'));price_receipt_sha256=(Get-PlanHash $PriceReceiptPath).ToLowerInvariant();notice='Retail estimate, not quote. Backup, disk operations, transfer, monitoring, tax and paid AI are additional. Budget alerts are not a hard spending cap.'};
  pending=@('Full integrated acceptance and security evidence','Subscription permission, quota, capacity, image and current quote','Owner-only RDP address and secure Windows credential entry','Dedicated service identities, ACLs, firewall and private PostgreSQL installation','Verified backup transfer/restore and service-owned secret provisioning','External owner approval manifest and Caddy proxy validation','Exact DNS and public TLS validation','Explicit approval before any chargeable resource creation or public launch')
 }
 if($PackageCode){
  $reviewStage='code-package'
  if((Get-PlanHash (Join-Path $planRoot 'main.json')) -cne (Get-PlanHash $compiled)){throw 'Regenerate and review main.json before packaging.'}
  $result['code_package']=New-CodeOnlyReviewPackage $workspace
 }
 $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
 Write-Output ('Offline plan verified. Public web remains closed. Review: '+[System.IO.Path]::GetFullPath($OutputPath))
} catch {
 # Avoid echoing any supplied parameter value or credential in an exception.
 Write-Output ('Offline Azure review failed at '+$reviewStage+'. Check the documented nonsecret parameters and pinned compiler; no cloud action was attempted.')
 exit 1
}
