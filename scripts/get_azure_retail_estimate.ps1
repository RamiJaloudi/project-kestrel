<# Read-only public pricing lookup. No login, resource creation or deployment. #>
param([ValidatePattern('^[a-z0-9]+$')][string]$Region='eastus2',[ValidateRange(1,744)][int]$Hours=730)
$ErrorActionPreference='Stop'
function Read-Retail([string]$Filter) {
    $uri='https://prices.azure.com/api/retail/prices?$filter='+[uri]::EscapeDataString($Filter)
    $items=@()
    do { $page=Invoke-RestMethod -Uri $uri; $items+=@($page.Items); $uri=$page.NextPageLink } while ($uri)
    return $items
}
$vm=Read-Retail "serviceName eq 'Virtual Machines' and armRegionName eq '$Region' and priceType eq 'Consumption' and (armSkuName eq 'Standard_B2as_v2' or armSkuName eq 'Standard_D2as_v5')"
$disks=Read-Retail "serviceName eq 'Storage' and armRegionName eq '$Region' and priceType eq 'Consumption' and productName eq 'Standard SSD Managed Disks'"
$ips=Read-Retail "serviceName eq 'Virtual Network' and armRegionName eq '$Region' and priceType eq 'Consumption' and productName eq 'IP Addresses'"
$rows=@()
foreach ($item in $vm | Where-Object { $_.productName -match 'Windows' -and $_.skuName -notmatch 'Spot|Low Priority' -and $_.currencyCode -eq 'USD' }) {
    $rows+=@{component=$item.armSkuName;meter=$item.meterName;rate=$item.retailPrice;unit=$item.unitOfMeasure;monthly=[math]::Round($item.retailPrice*$Hours,2);product=$item.productName}
}
foreach ($item in $disks | Where-Object { $_.meterName -in @('E10 LRS Disk','E6 LRS Disk','E10 LRS Disk Operations','E6 LRS Disk Operations','E10 LRS Disk Mount','E6 LRS Disk Mount') }) {
    $rows+=@{component='disk';meter=$item.meterName;rate=$item.retailPrice;unit=$item.unitOfMeasure;product=$item.productName}
}
foreach ($item in $ips | Where-Object { $_.meterName -eq 'Standard IPv4 Static Public IP' }) {
    $rows+=@{component='public_ipv4';meter=$item.meterName;rate=$item.retailPrice;unit=$item.unitOfMeasure;monthly=[math]::Round($item.retailPrice*$Hours,2);product=$item.productName}
}
@{queried_utc=[datetime]::UtcNow.ToString('o');region=$Region;hours=$Hours;currency='USD';source='https://prices.azure.com/api/retail/prices';scope='Retail PAYG estimate; not a quote, SKU quota check or resource deployment';items=$rows} | ConvertTo-Json -Depth 6
