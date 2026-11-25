// Candidate synthetic demo infrastructure. Public ingress is closed by default.
// This template installs no application and transfers no data or credentials.
targetScope = 'resourceGroup'

@description('Azure region; confirm quota and the actual quote before creation.')
param location string = 'eastus2'
@description('Small burstable Windows demo; not measured production capacity.')
@allowed(['Standard_B2as_v2'])
param vmSize string = 'Standard_B2as_v2'
@minLength(3)
@maxLength(12)
param vmName string = 'kestrel-demo'
@description('Windows owner login. Never use the application dummy password.')
param adminUsername string
@secure()
@minLength(16)
param adminPassword string
@description('Optional owner IPv4 address ONLY; template appends /32. Blank means no RDP ingress.')
param adminSourceIp string = ''
@description('Separate reviewed go-live gate. Keep false until explicit approval and security checks.')
param allowPublicWeb bool = false

var tags = {
  project: 'Project Kestrel'
  purpose: 'Synthetic candidate demonstration'
  dataClassification: 'Synthetic only'
}
var ownerRules = empty(adminSourceIp) ? [] : [{
  name: 'OwnerRdpOnly'
  properties: {
    priority: 100
    direction: 'Inbound'
    access: 'Allow'
    protocol: 'Tcp'
    sourcePortRange: '*'
    destinationPortRange: '3389'
    sourceAddressPrefix: '${adminSourceIp}/32'
    destinationAddressPrefix: '*'
  }
}]
var webRules = allowPublicWeb ? [{
  name: 'ReviewedWebIngress'
  properties: {
    priority: 200
    direction: 'Inbound'
    access: 'Allow'
    protocol: 'Tcp'
    sourcePortRange: '*'
    destinationPortRanges: ['80', '443']
    sourceAddressPrefix: 'Internet'
    destinationAddressPrefix: '*'
  }
}] : []
resource nsg 'Microsoft.Network/networkSecurityGroups@2022-05-01' = {
  name: '${vmName}-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: concat(ownerRules, webRules, [{
      name: 'DenyOtherInbound'
      properties: {
        priority: 4096
        direction: 'Inbound'
        access: 'Deny'
        protocol: '*'
        sourcePortRange: '*'
        destinationPortRange: '*'
        sourceAddressPrefix: '*'
        destinationAddressPrefix: '*'
      }
    }])
  }
}
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${vmName}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.42.0.0/24'] }
    subnets: [{
      name: 'application'
      properties: {
        addressPrefix: '10.42.0.0/27'
        // Explicit NIC public IP supplies egress; do not depend on implicit SNAT.
        defaultOutboundAccess: false
        networkSecurityGroup: { id: nsg.id }
      }
    }]
  }
}
resource publicIp 'Microsoft.Network/publicIPAddresses@2022-05-01' = {
  name: '${vmName}-ip'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static', publicIPAddressVersion: 'IPv4' }
}
resource nic 'Microsoft.Network/networkInterfaces@2022-05-01' = {
  name: '${vmName}-nic'
  location: location
  tags: tags
  properties: {
    enableIPForwarding: false
    ipConfigurations: [{
      name: 'application'
      properties: {
        privateIPAllocationMethod: 'Dynamic'
        publicIPAddress: { id: publicIp.id }
        subnet: { id: vnet.properties.subnets[0].id }
      }
    }]
  }
}
resource vm 'Microsoft.Compute/virtualMachines@2022-03-01' = {
  name: vmName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    hardwareProfile: { vmSize: vmSize }
    osProfile: {
      computerName: vmName
      adminUsername: adminUsername
      adminPassword: adminPassword
      windowsConfiguration: { provisionVMAgent: true, enableAutomaticUpdates: true }
    }
    storageProfile: {
      imageReference: {
        publisher: 'MicrosoftWindowsServer'
        offer: 'WindowsServer'
        sku: '2022-datacenter-g2'
        version: 'latest'
      }
      osDisk: {
        name: '${vmName}-os'
        createOption: 'FromImage'
        diskSizeGB: 128
        managedDisk: { storageAccountType: 'StandardSSD_LRS' }
        deleteOption: 'Detach'
      }
      dataDisks: [{
        name: '${vmName}-data'
        lun: 0
        diskSizeGB: 64
        createOption: 'Empty'
        managedDisk: { storageAccountType: 'StandardSSD_LRS' }
        caching: 'None'
        deleteOption: 'Detach'
      }]
    }
    networkProfile: { networkInterfaces: [{ id: nic.id, properties: { deleteOption: 'Detach' } }] }
    securityProfile: {
      securityType: 'TrustedLaunch'
      uefiSettings: { secureBootEnabled: true, vTpmEnabled: true }
    }
    diagnosticsProfile: { bootDiagnostics: { enabled: true } }
  }
}
output publicIpv4 string = publicIp.properties.ipAddress
output vmResourceId string = vm.id
output approvedPortalHosts array = [
  'portal.ramijaloudi.com'
  'firm.portal.ramijaloudi.com'
  'halden.portal.ramijaloudi.com'
  'castlegate.portal.ramijaloudi.com'
  'admin.portal.ramijaloudi.com'
]
output publicWebRequested bool = allowPublicWeb
