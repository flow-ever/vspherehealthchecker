from pyVmomi import vim
import os 
import json
import datetime
import logging
from pyVim.connect import Disconnect,SmartConnectNoSSL
import atexit
import sys
import vsanmgmtObjects
import vsanapiutils
from packaging.version import Version
from decimal import Decimal
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import pytz

# vc 11
# -- --
#  | |____sequence number
#  |_______managed object type:
#                                 vc--vcenter
#                                 dc--datacenter
#                                 cl--cluster
#                                 hs--host
#                                 rp--resourcepool
#                                 vm--virtualmachine
#                                 va--vapp
#                                 nw--network
#                                 ds--datastore



def str2list(string):
    li=list(string.split(","))
    return li

def establish_connection(vchost,vcuser,vcpassword):
    try:
        si = SmartConnectNoSSL(host=vchost, user=vcuser, pwd=vcpassword)
        atexit.register(Disconnect, si)
        return si
    except Exception as e:
        print(f"Failed to connect to vCenter at {vchost}: {e}")
        logger.error(f"Failed to connect to vCenter at {vchost}: {e}")
        return None



class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            print("MyEncoder-datetime.datetime")
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(obj, bytes):
            return str(obj, encoding='utf-8')
        if isinstance(obj, int):
            return int(obj)
        elif isinstance(obj, float):
            return float(obj)
        #elif isinstance(obj, array):
        #    return obj.tolist()
        else:
            return super(MyEncoder, self).default(obj)


# Capture ESXi host physical nics
def get_host_pnics(host):
    host_pnics = []
    for pnic in host.config.network.pnic:
        pnic_info = dict()
        pnic_info.update(
            {'device': pnic.device, 'driver': pnic.driver, 'mac': pnic.mac})
        host_pnics.append(pnic_info)

    return host_pnics

# Capture ESXi host virtual nics
def get_host_vnics(host):
    host_vnics = []
    for vnic in host.config.network.vnic:
        vnic_info = dict()
        vnic_info.update(
            {'device': vnic.device, 'portgroup': vnic.portgroup,
             'dhcp': vnic.spec.ip.dhcp, 'ipAddress': vnic.spec.ip.ipAddress,
             'subnetMask': vnic.spec.ip.subnetMask,
             'mac': vnic.spec.mac, 'mtu': vnic.spec.mtu})
        host_vnics.append(vnic_info)
    return host_vnics

def get_host_portgroups(host):
    host_portgroups = []
    for portgroup in host.config.network.portgroup:        
        if isinstance(portgroup.spec.policy.nicTeaming,type(None)):
            pg_nicteaming_policy=""
        else:
            pg_nicteaming_policy=portgroup.spec.policy.nicTeaming.policy
        
        if isinstance(portgroup.spec.policy.security,type(None)):
            pg_sec_ap=""
            pg_sec_macc=""
            pg_sec_ft=""
        else:
            pg_sec_ap=portgroup.spec.policy.security.allowPromiscuous
            pg_sec_macc=portgroup.spec.policy.security.macChanges
            pg_sec_ft=portgroup.spec.policy.security.forgedTransmits

        portgroup_info = dict()
        portgroup_info.update(
            {'name': portgroup.spec.name, 'vlanId': portgroup.spec.vlanId,
             'vswitchName': portgroup.spec.vswitchName,
             'nicTeamingPolicy': pg_nicteaming_policy,
             'allowPromiscuous': pg_sec_ap,
             'macChanges': pg_sec_macc,
             'forgedTransmits': pg_sec_ft})
        host_portgroups.append(portgroup_info)

    return host_portgroups

# Capture ESXi host virtual switches
def get_host_vswitches(host):
    host_vswitches = []
    for vswitch in host.config.network.vswitch:
        vswitch_info = dict()
        vswitch_pnics = []
        vswitch_portgroups = []
        for pnic in vswitch.pnic:
            pnic = pnic.replace('key-vim.host.PhysicalNic-', '')
            vswitch_pnics.append(pnic)
        for pg in vswitch.portgroup:
            pg = pg.replace('key-vim.host.PortGroup-', '')
            vswitch_portgroups.append(pg)
        vswitch_info.update(
            {'name': vswitch.name, 'pnics': vswitch_pnics,
             'portgroups': vswitch_portgroups, 'mtu': vswitch.mtu})
        host_vswitches.append(vswitch_info)

    return host_vswitches

def get_hosts_portgroups(hosts):
    host_pg_dict={}
    for host in hosts:
        host_pg_dict[host]=host.config.network.portgroup
    return host_pg_dict

def get_host_datetime(host):
#    print(host)
   host_datetime_info={}
#    host_datetime_info['enabled']=host.config.dateTimeInfo.enabled
#    host_datetime_info['lastSyncTime']=host.config.dateTimeInfo.lastSyncTime
   host_datetime_info['ntpServer']=host.config.dateTimeInfo.ntpConfig.server  #server[]
   return host_datetime_info

def counterID2Name(content,counterId):
    perfManager = content.perfManager
    perf_dict = {}
    perf_list = perfManager.perfCounter
    for counter in perf_list:
        counter_fullName = "{}.{}.{}".format(counter.groupInfo.key, counter.nameInfo.key, counter.rollupType)
        perf_dict[counter.key] =counter_fullName  # perf_dict包含了所有的perfCounter
    if perf_dict.get(counterId) is not None:
        return perf_dict.get(counterId)
    else:
        return None

def buildQuery(content, vchtime, counternames, instance, obj):
    perfManager = content.perfManager
    perf_dict = {}
    perf_list = perfManager.perfCounter
    for counter in perf_list:
        counter_fullName = "{}.{}.{}".format(counter.groupInfo.key, counter.nameInfo.key, counter.rollupType)
        perf_dict[counter_fullName] = counter.key # perf_dict包含了所有的perfCounter

    #注意，counterId在不同主机上表示的指标项可能不一样，但是counterName不会变化，所以查询要以countername为依据
    counterIds=[perf_dict[counter_fullName] for counter_fullName in counternames ]
    if instance=="" or instance is None:
         instance="*"
    # instance=""
    metricId = [vim.PerformanceManager.MetricId(counterId=counterId, instance=instance) for counterId in counterIds]
    startTime = vchtime - datetime.timedelta(days=1)
    endTime = vchtime - datetime.timedelta(minutes=1)
    query = vim.PerformanceManager.QuerySpec(intervalId=20, entity=obj, metricId=metricId, startTime=startTime,
                                             endTime=endTime)
    perfResults = perfManager.QueryPerf(querySpec=[query])
    
    if perfResults:
        return perfResults
    else:
        print('ERROR: Performance results empty.  TIP: Check time drift on source and vCenter server')
        print('Troubleshooting info:')
        print('vCenter/host date and time: {}'.format(vchtime))
        print('Start perf counter time   :  {}'.format(startTime))
        print('End perf counter time     :  {}'.format(endTime))
        print(query)
        # exit()
        return perfResults


# Method that populates objects of type vimtype
def get_all_objs(content, vimtype):
    obj = []
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for managed_object_ref in container.view:
        # obj.update({managed_object_ref: managed_object_ref.name})
        obj.append(managed_object_ref)
    return obj

def QueryDCsInfo(vchost,vcuser,vcpassword):
    cwd = os.getcwd()
    current_time=datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    dc_json_file=os.path.join(cwd,'data',"dc-"+current_time+".json")

    logfile_path=os.path.join(cwd,'data','log',"dcInfo_gathering.log")
    log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
    logger=logging.getLogger('DC_logger')
    fh=logging.FileHandler(filename=logfile_path,mode='w')
    fh.setLevel(logging.INFO)
    fh.setFormatter(log_formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)

    si=establish_connection(vchost,vcuser,vcpassword)
    content=si.content
    print("Gathering vSphere Datacenters information")
    logger.info("开始收集Datacenter信息!")

    vcenter={}
    vcenter['name']=vchost
    vcenter['id']='vc1'
    vcenter['path']=vcenter['id']
    vcenter['type']='vcenter'

    dcs=get_all_objs(content,[vim.Datacenter])
    datacenters=[]
    dc_no=0
    for dc in dcs:
        logger.info("开始收集Datacenter："+ dc.name+" 信息")
        dc_config={}
        dc_config['type']='datacenter'
        dc_no+=1
        dc_config['id']='dc'+str(dc_no)
        dc_config['path']=vcenter['path']+'-'+dc_config['id']
        dc_config['parent']=vcenter['id']
        sub_clusters=[]
        
        
        vdss=[]
        nw_no=0
        for cls in dc.networkFolder.childEntity:
            if isinstance(cls,vim.DistributedVirtualSwitch):
                # print(cls.name)  # dvs name
                vds={}
                vds['name']=cls.name
                nw_no+=1
                vds['id']='nw'+str(nw_no)
                vds['path']=dc_config['path']+'-'+vds['id']
                vds['type']='network'
                vds['parent']=dc_config['id']
                
                portgroups=[]
                pg_no=0
                for pg in  cls.portgroup:
                    portgroup={}     # Portgroups that are defined on the switch.[]
                    # print(pg.name)
                    # print(pg.key) 
                    # print(pg.config)
                    portgroup['name']=pg.name
                    pg_no+=1
                    portgroup['id']='pg'+str(pg_no)
                    portgroup['path']=vds['path']+'-'+portgroup['id']
                    portgroup['parent']=vds['id']
                    vlaninfo=pg.config.defaultPortConfig.vlan
                    if isinstance(vlaninfo,vim.dvs.VmwareDistributedVirtualSwitch.TrunkVlanSpec):  #端口组为trunk类型
                        vlanlist=[]
                        for item in vlaninfo.vlanId:
                            if item.start==item.end:
                                vlanlist.append(str(item.start))
                            else:
                                vlanlist.append(str(item.start)+'-'+str(item.end))
                        portgroup['vlan_id']=','.join(vlanlist)
                    else:
                        portgroup['vlan_id']=str(vlaninfo.vlanId)

                    # if isinstance(vlanId,list):
                    #     if vlanId[0].start==0 and vlanId[0].end==4094:
                    #         vlanId=4095
                    # portgroup['vlan']=vlanId

                    # print(vlanId)
                    portgroup['uplinkTeamingPolicy']={"value":pg.config.defaultPortConfig.uplinkTeamingPolicy.policy.value,"inherited":pg.config.defaultPortConfig.uplinkTeamingPolicy.policy.inherited}
                    portgroup['uplinkPortOrder']={"activeUplinkPort":pg.config.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.activeUplinkPort, \
                                                  "standbyUplinkPort":pg.config.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.standbyUplinkPort, \
                                                    "inherited":pg.config.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.inherited}

                    portgroup['uplink']=pg.config.uplink
                    portgroups.append(portgroup)
                vds['portgroups']=portgroups
                
                # for hostmember in cls.config.host:
                #     print(cls.name+"--"+hostmember.config.host.name)
                connectedHosts=[]
                for host in cls.config.host:
                    connectedHosts.append(host.config.host.name)
                vds['connectedHosts']=connectedHosts
                vdss.append(vds)

        ds_no=0
        datastores=[]
        for ds in dc.datastoreFolder.childEntity:
            ds_info={}
            ds_info['name']=ds.name
            ds_no+=1
            ds_info['id']='ds'+str(ds_no)
            ds_info['path']=dc_config['path']+'-'+ds_info['id']
            ds_info['hosts']=ds.host #Hosts attached to this datastore.
            ds_info['vm']=ds.vm
            ds_info['maxVirtualDiskCapacity']=ds.info.maxVirtualDiskCapacity #The maximum capacity of a virtual disk which can be created on this volume.
            ds_info['capacity']=ds.summary.capacity  #Maximum capacity of this datastore, in bytes. 
            ds_info['freeSpace']=ds.summary.freeSpace #Free space of this datastore, in bytes.
            ds_info['multipleHostAccess']=ds.summary.multipleHostAccess
            ds_info['fstype']=ds.summary.type
            ds_info['type']='datastore'
            ds_info['uncommited']=ds.summary.uncommitted if ds.summary.uncommitted else 0 #Total additional storage space, in bytes, potentially used by all virtual machines on this datastore. 
            ds_info['provisioned']=ds.summary.capacity-ds.summary.freeSpace+ds.summary.uncommitted

            datastores.append(ds_info)

        cl_no=0
        for cls in dc.hostFolder.childEntity:
            if isinstance(cls,vim.ClusterComputeResource):
                cl_no+=1
                cluster_config={}
                hosts=[]
                vsan_info={}
                cluster_config['name']=cls.name
                cluster_config['type']='cluster'
                cluster_config['id']='cl'+str(cl_no)
                cluster_config['path']=dc_config['path']+'-'+cluster_config['id']

                cluster_config['parent']=dc_config['id']
                
                hs_no=0
                for sub_host in cls.host:
                    hs_no+=1
                    host={}
                    host['name']=sub_host.name
                    host['id']='hs'+str(hs_no)
                    host['path']=cluster_config['path']+'-'+host['id']
                    host['parent']=cluster_config['id']


                    logger.info("开始收集esxi主机信息："+ sub_host.name)
                    
                    host_BASIC=[]
                    host_BIOSINFO=[]
                    host_CPU_RAM_CONFIG=[]
                    host_CPU_RAM_USAGE=[]
                    host_STORAGE_DS=[]
                    host_STORAGE_MULTIPATH=[]
                    host_STORAGE_HBA=[]
                    host_STORAGE_LUN=[]
                    host_PNIC=[]

                    timezones=sub_host.configManager.dateTimeSystem.QueryAvailableTimeZones()
                    host['timezone']=timezones[0].name
                    host_datetime=sub_host.configManager.dateTimeSystem.QueryDateTime()
                    deviation=abs(datetime.datetime.now(pytz.utc)-host_datetime.replace(tzinfo=pytz.utc)).total_seconds()
                    host['deviation']=Decimal(deviation).quantize(Decimal("0"))

                    # host['host']=host.summary.config.name
                    #获取证书
                    logger.info("开始收集esxi主机"+ sub_host.name+"证书信息：")
                    pem=""
                    for byte in sub_host.config.certificate:
                        pem=pem+chr(byte)
                    cert=x509.load_pem_x509_certificate(pem.encode(), default_backend())
                    #  print('Valid from ' + str(cert.not_valid_before) + ' to ' + str(cert.not_valid_after))
                    cert_info = sub_host.configManager.certificateManager.certificateInfo
                    #    print(type(cert.not_valid_after))  
                    #    if abs((cert_info.notAfter.date()-datetime.date.today()).days)>180:
                    #        print(" Certificate Subject:"+cert_info.subject+' Valid from ' + str(cert_info.notBefore) + ' to ' + str(cert_info.notAfter))
                    #     #    print(abs((cert_info.notAfter.date()-datetime.date.today()).days))
                    
                    cert={}
                    cert['subject']=cert_info.subject
                    cert['sign_date']=cert_info.notBefore.strftime('%Y-%m-%d %H:%M:%S')
                    cert['expired_date']=cert_info.notAfter.strftime('%Y-%m-%d %H:%M:%S')

                    host['certificate']=cert

                        #获取NTP
                    host['datetime_info']=get_host_datetime(sub_host)
                    #    print(dateinfo['ntpServer'])

                    #获取：
                    #name:host.summary.config.name

                    #managementIP:host.summary.managementServerIp
                    #model: host.summary.hardware.model
                    #vendor:host.summary.hardware.vendor
                    #serialnumber: host.hardwareInfo.systemInfo.serialNumber
                    #BIOS info: host.hardwareInfo.biosInfo
                    #CPU model:  host.summary.hardware.cpuModel
                    #CPU Frequency:  host.summary.hardware.cpuMhz
                    #Total physical CPU cores:host.summary.hardware.numCpuCores
                    #Total physical CPU threads:host.summary.hardware.numCpuThreads
                    #Total of HBAs: host.summary.hardware.numHBAs
                    #Total of NICs: host.summary.hardware.numNics
                    #physical memory size in byte: host.summary.hardware.memorySize
                    # CPU usage: host.summary.quickStats.overallCpuUsage
                    #Memory usage: host.summary.quickStats.overallMemoryUsage
                    #Uptime: host.summary.quickStats.uptime
                    #evc mode in effect: host.summary.currentEVCModeKey
                    #esxi version:host.config.product.fullName
                    #esxi build:host.config.product.build
                    #esxi patchlevel:host.config.product.patchLevel
                    #esxi licenseProductName:host.config.product.licenseProductName
                    #esxi licenseProductVersion:host.config.product.licenseProductVersion
                    #vMotionenabled:host.summary.config.vmotionEnabled

                    #host multipath info: host.config.multipathState.path[name,pathState]
                    #host datastore: host.datastore.summary.name
                    #host datastore: host.datastore.summary.accessible  
                    #host datastore capacity in bytes: host.datastore.summary.capacity
                    #host datastore freespace in bytes: host.datastore.summary.freeSpace
                    #host datastore: host.datastore.summary.multipleHostAccess
                    #host datastore: host.datastore.summary.type
                    
                    vm_no=0
                    vm_name_list=[]
                    for vm in sub_host.vm:
                        vm_no+=1
                        vm_config={}
                        vm_config['name']=vm.name
                        vm_config['Powerstate']=vm.runtime.powerState
                        vm_config['id']='vm'+str(vm_no)
                        vm_config['path']=host['path']+'-'+vm_config['id']
                        vm_config['parent']=host['id']
                        vm_name_list.append(vm_config)

                    host['vm_list']=vm_name_list

                    numVms=len(vm_name_list)
                    
                    numPoweron=0
                    numvCPUs=0
                    for i in range(numVms):
                        
                        if vm_name_list[i]['Powerstate']=="poweredOn":
                            numPoweron+=1
                            numvCPUs+=sub_host.vm[i].summary.config.numCpu

                    host['numVms']=numVms
                    host['numPoweronVMs']=numPoweron

                    # host['numvCPUs']=numvCPUs

                    #    print("numPoweron/numVms:"+str(numPoweron)+"/"+str(numVms)) 
                    host_basic_info={}
                    #    host_basic_info['host']=host.summary.config.name
                    host_basic_info['mgmtIP']=sub_host.summary.managementServerIp
                    host_basic_info['vendor']=sub_host.summary.hardware.vendor
                    host_basic_info['model']=sub_host.summary.hardware.model
                    host_basic_info['sn']=sub_host.hardware.systemInfo.serialNumber
                    host_basic_info['biosInfo']=sub_host.hardware.biosInfo.biosVersion+"|"+str(sub_host.hardware.biosInfo.releaseDate)
                    host_basic_info['esxi']=sub_host.config.product.fullName
                    host_basic_info['uptime']=Decimal(sub_host.summary.quickStats.uptime/3600).quantize(Decimal("0.0"))
                    host_BASIC.append(host_basic_info)
                    host['basic_info']=host_BASIC

                    host_bios_info={}
                    #    host_bios_info['host']=host.summary.config.name
                    host_bios_info['biosVersion']=sub_host.hardware.biosInfo.biosVersion
                    host_bios_info['releaseDate']=str(sub_host.hardware.biosInfo.releaseDate.strftime("%m/%d/%Y"))
                    host_bios_info['firmwareMajorRelease']=sub_host.hardware.biosInfo.firmwareMajorRelease
                    host_bios_info['firmwareMinorRelease']=sub_host.hardware.biosInfo.firmwareMinorRelease
                    #    host_bios_info['majorRelease']=host.hardware.biosInfo.majorRelease
                    #    host_bios_info['minorRelease']=host.hardware.biosInfo.minorRelease
                    host_BIOSINFO.append(host_bios_info)
                    host['bios_info']=host_BIOSINFO
                    #    print(host_bios_info) 

                    cpu_ram_config={}
                    #    cpu_ram_config['host']=host.summary.config.name
                    cpu_ram_config['cpuModel']=sub_host.summary.hardware.cpuModel
                    cpu_ram_config['cpuMhz']=sub_host.summary.hardware.cpuMhz
                    cpu_ram_config['numCpuCores']=sub_host.summary.hardware.numCpuCores
                    cpu_ram_config['numCpuThreads']=sub_host.summary.hardware.numCpuThreads
                    cpu_ram_config['ramSize']=Decimal(sub_host.summary.hardware.memorySize/1024/1024/1024).quantize(Decimal("0.0"))
                    host_CPU_RAM_CONFIG.append(cpu_ram_config)
                    host['cpu_ram_config']=host_CPU_RAM_CONFIG
                    
                    cpu_ram_usage={}
                    #    cpu_ram_usage['host']=host.summary.config.name
                    cpu_ram_usage['consolidate_ratio']=Decimal(numvCPUs/sub_host.summary.hardware.numCpuCores).quantize(Decimal("0.0"))
                    cpu_ram_usage['cpu_usage']=Decimal(sub_host.summary.quickStats.overallCpuUsage/sub_host.summary.hardware.cpuMhz/sub_host.summary.hardware.numCpuCores).quantize(Decimal("0.000"))
                    cpu_ram_usage['ram_usage']=Decimal(sub_host.summary.quickStats.overallMemoryUsage*1024*1024/sub_host.summary.hardware.memorySize).quantize(Decimal("0.000"))
                    #    print(cpu_ram_usage)

                    host_CPU_RAM_USAGE.append(cpu_ram_usage)
                    host['cpu_ram_usage']=host_CPU_RAM_USAGE      


                    for ds in sub_host.datastore:
                            datastore={}
                            # print("datatore name:"+ds.summary.name+" \
                            #         capacity:"+str(round(ds.summary.capacity/1024/1024/1024,0))+"GB \
                            #             Free Space:"+str(round(ds.summary.freeSpace/1024/1024/1024,0))+"GB \
                            #                 multipleHostAccess:"+str(ds.summary.multipleHostAccess)+" \
                            #                     Type:"+ds.summary.type)
                            # datastore['host']=host.summary.config.name
                            datastore['datatore name']=ds.summary.name
                            datastore['capacity']=str(Decimal(ds.summary.capacity/1024/1024/1024).quantize(Decimal("0")))
                            datastore['free space']=str(Decimal(ds.summary.freeSpace/1024/1024/1024).quantize(Decimal("0")))
                            datastore['multipleHostAccess']=str(ds.summary.multipleHostAccess)
                            datastore['type']=ds.summary.type
                            
                            host_STORAGE_DS.append(datastore)
                    host['datastores']=host_STORAGE_DS


                    #    print("esxi version:"+host.config.product.fullName)
                    #    print("esxi build:"+host.config.product.build)
                    #    print("esxi patchLevel:"+host.config.product.patchLevel)
                    #    print("esxi licenseProductName:"+host.config.product.licenseProductName)
                    #    print("esxi licenseProductVersion:"+host.config.product.licenseProductVersion)

                    
                    if len(sub_host.config.storageDevice.hostBusAdapter)>0:
                        for adpt in sub_host.config.storageDevice.hostBusAdapter:
                            hba={}
                            #  print("hba device:"+adpt.device+" hba model:"+adpt.model+" driver:"+adpt.driver+" storage protocol:"+adpt.storageProtocol)
                            #  hba['host']=host.summary.config.name
                            hba['name']=adpt.device
                            hba['model']=adpt.model
                            hba['driver']=adpt.driver
                            hba['protocol']=adpt.storageProtocol
                            host_STORAGE_HBA.append(hba)
                    host['hbas']=host_STORAGE_HBA
                    
                    
                    if len(sub_host.config.storageDevice.scsiLun)>0:
                        for scsi_lun in sub_host.config.storageDevice.scsiLun:
                            scsilun={}
                            # print("display name:"+scsi_lun.displayName+" lunType:"+scsi_lun.lunType+" model:"+scsi_lun.model)
                            # scsilun['host']=host.summary.config.name
                            scsilun['displayName']=scsi_lun.displayName
                            scsilun['lunType']=scsi_lun.lunType
                            scsilun['model']=scsi_lun.model
                            host_STORAGE_LUN.append(scsilun)
                    host['scsi_lun']=host_STORAGE_LUN   


                    
                    for path in sub_host.config.multipathState.path:
                        multipath={}
                        #   print("path name:"+path.name +" path state:"+path.pathState)
                        #   multipath['host']=host.summary.config.name
                        multipath['path name']=path.name
                        multipath['path state']=path.pathState
                        host_STORAGE_MULTIPATH.append(multipath)
                    host['multipaths']=host_STORAGE_MULTIPATH
                    
                    # for vsw in host.config.network.vswitch:
                    #    vswitch={}
                    #  #   print("key:"+vsw.key+" Name:"+vsw.name+" \
                    #  #         MTU:"+str(vsw.mtu)+" PNIC list："+"|".join(vsw.pnic)+" \
                    #  #             portgroup:"+"|".join(vsw.portgroup))
                    #  #   vswitch['host']=host.summary.config.name
                    #    vswitch['vswitch name']=vsw.name
                    #    vswitch['uplink pnics']="|".join(vsw.pnic)
                    #    vswitch['mtu']=vsw.mtu
                    #    vswitch['portgroup']="|".join(vsw.portgroup)
                    #    host_VSWITCH.append(vswitch)
                    # host['vswitches']=host_VSWITCH
                    host['vswitches']=get_host_vswitches(sub_host)

                    for pnic in sub_host.config.network.pnic:
                            p_nic={}
                        #   print(pnic)
                            # p_nic['host']=host.summary.config.name
                            p_nic['name']=pnic.device
                            p_nic['mac']=pnic.mac
                            p_nic['driver']=pnic.driver
                            p_nic['autoNego']=str(pnic.autoNegotiateSupported) 
                            if pnic.linkSpeed is not None:
                                # print("key:"+pnic.key+" device:"+pnic.device+" \
                                #         Driver:"+pnic.driver+" PNIC Speed："+str(pnic.linkSpeed.speedMb)+" \
                                #             duplex:"+str(pnic.linkSpeed.duplex)+" \
                                #             mac:"+pnic.mac+" \
                                #                 Nego:"+str(pnic.autoNegotiateSupported))
                                p_nic['speedMb']=pnic.linkSpeed.speedMb
                                p_nic['duplex']=pnic.linkSpeed.duplex                               
                            else:
                                p_nic['speedMb']=""
                                p_nic['duplex']=""
                            host_PNIC.append(p_nic)
                    host['pnics']=host_PNIC       
                        
                    host['vnics']=get_host_vnics(sub_host)
                    
                    CPU_disk_metrics=[]
                    network_metrics=[]
                    vchtime=si.CurrentTime()
                        # Get all available metric IDs and instances for this host
                        # counter_ids=[m.counterId for m in perf_manager.QueryAvailableMetric(entity=host)]
                        # instances=[m.instance for m in perf_manager.QueryAvailableMetric(entity=host) ]
                        # # #retrieve the perf counter name and counter_id mapping relationship
                        # perf_counter_infor=perf_manager.QueryPerfCounter(counter_ids)
                        # print(perf_counter_infor)

                        # Using the IDs form a list of MetricId
                        # objects for building the Query Spec    
                        # metric_ids=[vim.PerformanceManager.MetricId(counterId=counter,instance="*") for counter in counter_ids]

                        #counter name:net.usage.average,net.usage.maximum,net.throughput.usage.average
                    counter_names=['net.usage.average','net.usage.maximum','net.throughput.usage.average']
                    instance=""


                        # # Query the performance manager
                        # # based on the metrics created above    
                    result_stats=buildQuery(content, vchtime, counter_names,instance,sub_host)
                    
                    for instance_metric in result_stats:
                            values=instance_metric.value
                            for v in values:
                                network_metric={}

                                network_metric["counterId"]=v.id.counterId
                                network_metric["countername"]=counterID2Name(content,v.id.counterId)
                                network_metric["endTime"]=vchtime.astimezone()
                                if v.id.instance=="":
                                    network_metric["instance"]="all"
                                else:
                                    network_metric["instance"]=v.id.instance
                                network_metric["value"]=[value for value in v.value]
                                metric_time=[]
                                endTime = vchtime.astimezone() - datetime.timedelta(minutes=1)
                                for i in range(len(network_metric["value"])):
                                    metric_time.append((endTime-datetime.timedelta(seconds=i*20)).strftime("%m/%d/%Y %H:%M:%S"))
                                metric_time.reverse()
                                network_metric['endTime']=metric_time
                                network_metrics.append(network_metric)
                    #    print(network_metrics)
                    host['network_metrics']=network_metrics               


                    #'cpu.usage.average','cpu.readiness.average','disk.maxTotalLatency.latest'
                    counter_names=['cpu.usage.average','cpu.readiness.average','disk.maxTotalLatency.latest'] 
                    instance=""  
                    result_stats=buildQuery(content, vchtime, counter_names,instance,sub_host)
                        # print(result_stats)
                    for instance_metric in result_stats:
                            values=instance_metric.value
                            for v in values:
                                metric={}                
                                if v.id.instance=="":
                                    metric["endTime"]=vchtime.astimezone()
                                    metric["counterId"]=v.id.counterId
                                    metric["countername"]=counterID2Name(content,v.id.counterId)
                                    if v.id.counterId==6:
                                        metric["value"]=[Decimal(value*100/(sub_host.summary.hardware.numCpuCores*sub_host.summary.hardware.cpuMhz)).quantize(Decimal(0.00)) for value in v.value]
                                    elif v.id.counterId==12:
                                        metric["value"]=[Decimal(value*100/(20*1000)).quantize(Decimal(0.00)) for value in v.value]
                                    else:
                                        metric["value"]=[value for value in v.value]
                                    metric_time=[]
                                    endTime = vchtime.astimezone() - datetime.timedelta(minutes=1)
                                    for i in range(len(metric["value"])):
                                        metric_time.append((endTime-datetime.timedelta(seconds=i*20)).strftime("%m/%d/%Y %H:%M:%S"))
                                    metric_time.reverse()    
                                    metric['endTime']=metric_time
                                    CPU_disk_metrics.append(metric)
                    #    print(CPU_disk_metrics)
                    host['CPU_disk_metrics']=CPU_disk_metrics

                    hosts.append(host)
                
                

                #收集集群信息
                logger.info("开始收集集群："+ cls.name +" HA信息")
                ha_config={}   
                advancedSettings=[]
                advancedSetting={}
                # if len(cls.configurationEx.dasConfig.option)>0:
                
                    
                for item in cls.configurationEx.dasConfig.option:
                        advancedSetting[item.key]=item.value
                        advancedSettings.append(advancedSetting)
                
                


                ha_config.update(
                                    {
                                        
                                        "admissionControlEnabled":cls.configurationEx.dasConfig.admissionControlEnabled,
                                        "resourceReductionToToleratePercent":cls.configurationEx.dasConfig.admissionControlPolicy.resourceReductionToToleratePercent,
                                        "cpuFailoverResourcesPercent":cls.configurationEx.dasConfig.admissionControlPolicy.cpuFailoverResourcesPercent,
                                        "memoryFailoverResourcesPercent":cls.configurationEx.dasConfig.admissionControlPolicy.memoryFailoverResourcesPercent,
                                        "vmRestartPriority":cls.configurationEx.dasConfig.defaultVmSettings.restartPriority,
                                        "vmRestartPriorityTimeout":cls.configurationEx.dasConfig.defaultVmSettings.restartPriorityTimeout,
                                        "vmIsolationResponse":cls.configurationEx.dasConfig.defaultVmSettings.isolationResponse,
                                        "enabled":cls.configurationEx.dasConfig.enabled,
                                        "heartbeatDatastore":cls.configurationEx.dasConfig.heartbeatDatastore,
                                        "enabled":cls.configurationEx.dasConfig.enabled,
                                        "hostMonitoring":cls.configurationEx.dasConfig.hostMonitoring,
                                        "vmMonitoring":cls.configurationEx.dasConfig.vmMonitoring,
                                        "advancedSettings":advancedSettings
                                    }
                                )
            #    print(ha_config_dic)

            #retrive drs configurationEx 
                logger.info("开始收集集群："+ cls.name +" DRS信息")   
                drs_config={}   
                drs_config.update(
                                    {   
                                        "vmotionRate":cls.configurationEx.drsConfig.vmotionRate,
                                        "defaultVmBehavior":cls.configurationEx.drsConfig.defaultVmBehavior,
                                        "enableVmBehaviorOverrides":cls.configurationEx.drsConfig.enableVmBehaviorOverrides,

                                    }
                                )  
            
            #retrive evc configuration 
                logger.info("开始收集集群："+ cls.name +" EVC信息")   
                evc_config={}
                evc_cluster_manager=cls.EvcManager()

                evc_state=evc_cluster_manager.evcState
                current_evcmode_key= evc_state.currentEVCModeKey
                if(current_evcmode_key):
                        
                        evc_config['EVCMode']=current_evcmode_key
                        evc_config['enabled']=True

                else:
                        evc_config['EVCMode']="N/A"
                        evc_config['enabled']=False
                        # quit()

                # feature_capabilities = evc_state.featureCapability

                # for capability in feature_capabilities:
                #         print("Feature Capability\n") 
                #         print(capability.featureName) 
                #         print(capability.key) 
                #         print(capability.value) 
                #         print("-------------") 

                # features_masked = evc_state.featureMask

                # for mask in features_masked:
                #         print("Feature Masked\n") 
                #         print(mask.featureName) 
                #         print(mask.key) 
                #         print(mask.value) 
                #         print("-------------" )   

                cluster_config['name']=cls.name
                cluster_config['hosts']=hosts
                cluster_config['ha_config']=ha_config
                cluster_config['drs_config']=drs_config
                cluster_config['evc_config']=evc_config
            #    print(cluster_config['ha_config'])
                # clusters.append(cluster_config)

            #######################################################################################
            ##
            ## VSAN information 
            #######################################################################################
                
                aboutInfo = si.content.about
                # print(aboutInfo)
                if aboutInfo.apiType == 'VirtualCenter':
                    if Version(aboutInfo.apiVersion) < Version('6.7.1'):
                        print('The Virtual Center with version %s (lower than 6.7U3) is not '
                            'supported.' % aboutInfo.apiVersion)
                        # return -1
                apiVersion = vsanapiutils.GetLatestVmodlVersion(vchost)

                vcMos = vsanapiutils.GetVsanVcMos(
                    si._stub, context=None, version=apiVersion)

                vccs=vcMos['vsan-cluster-config-system']
                config=vccs.GetConfigInfoEx(cls)
                if config.enabled:
                    logger.info("开始收集集群："+ cls.name +" VSAN信息")   


                    # vsan cluster health check result
                    test_list=[]
                    vhs=vcMos['vsan-cluster-health-system']  #关联VSAN的群集健康管理对象
                    #获取当前vsan cluster支持的健康测试项目
                    support_tests=vhs.VsanQueryAllSupportedHealthChecks()

                    for test in support_tests:
                        test_dict={}
                        test_dict['groupName']=test.groupName
                        test_dict['groupId']=test.groupId
                        test_dict['testName']=test.testName
                        test_dict['testId']=test.testId     
                        
                        test_list.append(test_dict)
                    

                    #按照支持的健康测试项目，逐一测试
                    prefix='com.vmware.vsan.health.test.'
                    spec=vim.cluster.VsanHistoricalHealthQuerySpec()
                    end=datetime.datetime.utcnow() 
                    start=end - datetime.timedelta(hours=1) 
                    spec.end=end
                    spec.start=start
                    spec.clusters=[cls]
                    for test in test_list:
                        spec.groupId=prefix+test['groupId']
                        spec.testId=prefix+test['testId']
                        test_result=vhs.QueryClusterHistoricalHealth(spec)

                        if len(test_result)>0:
                            # print("test groupName:"+test_result[0].groups[0].groupName)
                            # print("test groupHealth:"+test_result[0].groups[0].groupHealth)
                            test["groupHealth"]=test_result[0].groups[0].groupHealth
                            # print("test testName:"+test_result[0].groups[0].groupTests[0].testName)
                            # print("test testShortDescription:"+test_result[0].groups[0].groupTests[0].testShortDescription)
                            test["testShortDescription"]=test_result[0].groups[0].groupTests[0].testShortDescription
                            # print("test testHealth:"+test_result[0].groups[0].groupTests[0].testHealth)
                            test["testHealth"]=test_result[0].groups[0].groupTests[0].testHealth
                            # print("test overallHealth:"+test_result[0].overallHealth)
                            test["overallHealth"]=test_result[0].overallHealth
                        else:
                            test["groupHealth"]=""
                            test["testShortDescription"]=""
                            test["testHealth"]=""
                            test["overallHealth"]=""
                    # print(test_list)
                    test_list.sort(key=lambda e:e['groupName']) #基于测试组名排序
                    vsan_info["health_test"]=test_list
                    #获取VSAN集群的磁盘信息
                    vdms=vcMos['vsan-disk-management-system']  

                    dataEfficientState=vdms.QueryClusterDataEfficiencyCapacityState(cls)
                    # print(dataEfficientState)
                    dataEfficientState_dict={}
                    dataEfficientState_dict['logicalCapacity']=dataEfficientState.logicalCapacity
                    dataEfficientState_dict['logicalCapacityUsed']=dataEfficientState.logicalCapacityUsed
                    dataEfficientState_dict['physicalCapacity']=dataEfficientState.physicalCapacity
                    dataEfficientState_dict['physicalCapacityUsed']=dataEfficientState.physicalCapacityUsed
                    dataEfficientState_dict['dedupMetadataSize']=dataEfficientState.spaceEfficiencyMetadataSize.dedupMetadataSize
                    dataEfficientState_dict['compressionMetadataSize']=dataEfficientState.spaceEfficiencyMetadataSize.compressionMetadataSize
                    vsan_info['dataEfficientState']=dataEfficientState_dict

                    #get disk map info 
                    cluster_diskMapInfo=[]
                    for host in cls.host:
                        diskmapping=vdms.QueryVsanManagedDisks(host)
                        host_diskMapInfo_dict={}
                        diskGroupMapInfo_list=[]

                        for diskgroupMapInfo in diskmapping.vSANDiskMapInfo:
                            diskGroupMapInfo_dict={}
                            ssdMapInfo_list=[]
                            ssdDiskMapInfo_dict={}
                            noSsdMapInfo_list=[]
                            noSsdDiskMapInfo_dict={}

                            
                            # print(diskgroupMapInfo)
                            ssd_info=diskgroupMapInfo.mapping.ssd
                            noSsd_info=diskgroupMapInfo.mapping.nonSsd
                            #hybrid 下diskgroup只有一个ssd，返回的ssd_info是一个dict类型。AF下返回的ssd_info是list类型
                            if not diskgroupMapInfo.isAllFlash:   #hybrid
                                ssdDiskMapInfo_dict['canonicalName']=ssd_info.canonicalName
                                ssdDiskMapInfo_dict['displayName']=ssd_info.displayName
                                ssdDiskMapInfo_dict['deviceType']=ssd_info.deviceType
                                ssdDiskMapInfo_dict['uuid']=ssd_info.uuid
                                ssdDiskMapInfo_dict['model']=ssd_info.model
                                ssdDiskMapInfo_dict['serialNumber']=ssd_info.serialNumber
                                ssdDiskMapInfo_dict['queueDepth']=ssd_info.queueDepth
                                ssdDiskMapInfo_dict['operationalState']=''.join(ssd_info.operationalState)  #[]
                                ssdDiskMapInfo_dict['capacity']=Decimal(ssd_info.capacity.blockSize*ssd_info.capacity.block/1000/1000/1000).quantize(Decimal(0)) #GB  
                                ssdDiskMapInfo_dict['physicalLocation']=''.join(ssd_info.physicalLocation)  #[]
                                ssdDiskMapInfo_dict['vsanUuid']=ssd_info.vsanDiskInfo.vsanUuid
                                ssdDiskMapInfo_dict['formatVersion']=ssd_info.vsanDiskInfo.formatVersion

                                ssdMapInfo_list.append(ssdDiskMapInfo_dict)

                                for noSsddisk in noSsd_info:
                                    noSsdDiskMapInfo_dict['canonicalName']=noSsddisk.canonicalName
                                    noSsdDiskMapInfo_dict['displayName']=noSsddisk.displayName
                                    noSsdDiskMapInfo_dict['deviceType']=noSsddisk.deviceType
                                    noSsdDiskMapInfo_dict['uuid']=noSsddisk.uuid
                                    noSsdDiskMapInfo_dict['model']=noSsddisk.model
                                    noSsdDiskMapInfo_dict['serialNumber']=noSsddisk.serialNumber
                                    noSsdDiskMapInfo_dict['queueDepth']=noSsddisk.queueDepth
                                    noSsdDiskMapInfo_dict['operationalState']=''.join(noSsddisk.operationalState)  #[]
                                    noSsdDiskMapInfo_dict['capacity']= Decimal(noSsddisk.capacity.blockSize*noSsddisk.capacity.block/1000/1000/1000).quantize(Decimal(0)) #GB
                                    noSsdDiskMapInfo_dict['physicalLocation']=''.join(noSsddisk.physicalLocation)  #[]
                                    noSsdDiskMapInfo_dict['vsanUuid']=noSsddisk.vsanDiskInfo.vsanUuid
                                    noSsdDiskMapInfo_dict['formatVersion']=noSsddisk.vsanDiskInfo.formatVersion

                                    noSsdMapInfo_list.append(noSsdDiskMapInfo_dict)
                            else:
                                for ssddisk in  ssd_info:
                                    ssdDiskMapInfo_dict['canonicalName']=ssd_info.canonicalName
                                    ssdDiskMapInfo_dict['displayName']=ssd_info.displayName
                                    ssdDiskMapInfo_dict['deviceType']=ssd_info.deviceType
                                    ssdDiskMapInfo_dict['uuid']=ssd_info.uuid
                                    ssdDiskMapInfo_dict['model']=ssd_info.model
                                    ssdDiskMapInfo_dict['serialNumber']=ssd_info.serialNumber
                                    ssdDiskMapInfo_dict['queueDepth']=ssd_info.queueDepth
                                    ssdDiskMapInfo_dict['operationalState']=''.join(ssd_info.operationalState)  #[]
                                    ssdDiskMapInfo_dict['capacity']=Decimal(ssd_info.capacity.blockSize*ssd_info.capacity.block/1000/1000/1000).quantize(Decimal(0)) #GB
                                    ssdDiskMapInfo_dict['physicalLocation']=''.join(ssd_info.physicalLocation)  #[]
                                    ssdDiskMapInfo_dict['vsanUuid']=ssd_info.vsanDiskInfo.vsanUuid
                                    ssdDiskMapInfo_dict['formatVersion']=ssd_info.vsanDiskInfo.formatVersion

                                    ssdMapInfo_list.append(ssdDiskMapInfo_dict)
                                

                            # diskGroupMapInfo_dict['host']=host.name                                   
                            diskGroupMapInfo_dict['isAllFlash']=diskgroupMapInfo.isAllFlash
                            diskGroupMapInfo_dict['isMounted']=diskgroupMapInfo.isMounted
                            diskGroupMapInfo_dict['isDataEfficiency']=diskgroupMapInfo.isDataEfficiency
                            diskGroupMapInfo_dict['ssdMapInfo']=ssdMapInfo_list
                            diskGroupMapInfo_dict['noSsdMapinfo']=noSsdMapInfo_list

                            diskGroupMapInfo_list.append(diskGroupMapInfo_dict)
                        host_diskMapInfo_dict['hostname']=host.name
                        host_diskMapInfo_dict['hostDiskMapInfo']=diskGroupMapInfo_list
                        cluster_diskMapInfo.append(host_diskMapInfo_dict)
                    cluster_diskMapInfo.sort(key=lambda e:e['hostname'])
                    # print(cluster_diskMapInfo)
                    vsan_info["cluster_disMapInfo"]=cluster_diskMapInfo
                    
                    #获取disk SMART 信息  
                    vchs = vcMos['vsan-cluster-health-system']
                    smartsData = vchs.VsanQueryVcClusterSmartStatsSummary(cluster=cls)

                    cluster_smartstat=[]
                    for data in smartsData:  #host
                        host_diskSmartstat_dict={}

                        host_diskSmartstat_list=[]
                        for smartStat in data.smartStats:  #disk 
                            # print("\nDisk: %s" % smartStat.disk)
                            smartDiskStat_dict={}#每个磁盘的smart统计信息
                            
                            smartStat_list=[]             
                            stats = smartStat.stats
                            for stat in stats:        #parameter
                                smartPara_dict={} #每个smart参数的统计信息
                                if stat.parameter:
                                    smartPara_dict['parameter']=stat.parameter
                                    smartPara_dict['value']=stat.value
                                    smartPara_dict['threshold']=stat.threshold
                                    smartPara_dict['worst']=stat.worst
                                    smartStat_list.append(smartPara_dict)

                            smartDiskStat_dict['disk']=smartStat.disk
                            smartDiskStat_dict['stats']=smartStat_list

                            host_diskSmartstat_list.append(smartDiskStat_dict)

                        host_diskSmartstat_dict['hostname']=data.hostname
                        host_diskSmartstat_dict['smartstat']=host_diskSmartstat_list

                        cluster_smartstat.append(host_diskSmartstat_dict)
                    cluster_smartstat.sort(key=lambda e:e['hostname'])
                    # print(cluster_smartstat)
                    vsan_info["cluster_diskSmartStat"]=cluster_smartstat


                    hosts_uuid_map=[]
                    for host in cls.host:
                        host_uuid_map={}
                        host_uuid_map['clusterUuid']=host.configManager.vsanSystem.config.clusterInfo.uuid
                        host_uuid_map['nodeUuid']=host.configManager.vsanSystem.config.clusterInfo.nodeUuid
                        host_uuid_map['hostname']=host.name
                        hosts_uuid_map.append(host_uuid_map)

                    #vsan 性能指标
                    vsan_perf={}
                    vpm=vcMos['vsan-performance-manager']
                    Spec = vim.cluster.VsanPerfQuerySpec()

                    entity_list=['virtual-machine','disk-group']
                    metricId_list=['iopsRead', 'iopsWrite', 'throughputRead', 'throughputWrite', 'latencyRead', 'latencyWrite']
                    # querySpec.entity=entity_list
                    # querySpec.metricId=metricId_list
                    # querySpec.entity='disk-group'
                    # querySpec.metricId="latencyRead"
                    # querySpec.numEntities=20
                    Spec.endTime = datetime.datetime.utcnow()
                    Spec.startTime = datetime.datetime.utcnow()-datetime.timedelta(hours=1)
                    entityType=['cluster-domclient','cluster-domcompmgr','host-domclient','host-domcompmgr','cache-disk','capacity-disk','disk-group','virtual-machine','vsan-host-net','vsan-pnic-net','vsan-cpu','vsan-memory']
                    # for entity in entityType:
                    #     Spec.entityRefId = entity+":*"
                    #     perf=vpm.QueryVsanPerf(querySpecs=[Spec],cluster=cls)

                        
                        # with open(logfile,'a') as f:
                        #     f.write("\n++++++++++++++++++++++++++++++++++++++++++++++"+entity+"++++++++++++++++++++++++++++++++++++++++++++++\n")
                        #     f.writelines(str(perf))
                        # f.close()
                    #虚拟机perf
                    Spec.entityRefId = entityType[0]+":"+hosts_uuid_map[0]['clusterUuid']
                    cls_frontend_perf=vpm.QueryVsanPerf(querySpecs=[Spec],cluster=cls)
                    cls_frontend_metric={}
                    for item in cls_frontend_perf:
                        cls_frontend_metric['sampleInfo']=str2list(item.sampleInfo)
                        for metric in item.value:
                            if metric.metricId.label=='iopsRead':
                                cls_frontend_metric['iopsRead']= str2list(metric.values)
                            if metric.metricId.label=='iopsWrite':
                                cls_frontend_metric['iopsWrite']= str2list(metric.values)
                            if metric.metricId.label=='throughputRead':
                                cls_frontend_metric['throughputRead']= str2list(metric.values)              
                            if metric.metricId.label=='throughputWrite':
                                cls_frontend_metric['throughputWrite']= str2list(metric.values)    
                            if metric.metricId.label=='latencyAvgRead':
                                cls_frontend_metric['latencyAvgRead']= str2list(metric.values)  
                            if metric.metricId.label=='latencyAvgWrite':
                                cls_frontend_metric['latencyAvgWrite']= str2list(metric.values) 
                            if metric.metricId.label=='congestion':
                                cls_frontend_metric['congestion']= str2list(metric.values)  
                    # vsan_perf.append({"cls_frontend_metric":cls_frontend_metric})
                    vsan_perf["cls_frontend_metric"]=cls_frontend_metric

                    #VSAN 后端perf
                    Spec.entityRefId = entityType[1]+":"+hosts_uuid_map[0]['clusterUuid']
                    cls_backend_perf=vpm.QueryVsanPerf(querySpecs=[Spec],cluster=cls)
                    cls_backend_metric={}
                    for item in cls_backend_perf:
                        cls_backend_metric['sampleInfo']=str2list(item.sampleInfo) 
                        for metric in item.value:
                            if metric.metricId.label=='iopsRead':
                                cls_backend_metric['iopsRead']= str2list(metric.values) 
                            if metric.metricId.label=='iopsWrite':
                                cls_backend_metric['iopsWrite']= str2list(metric.values)  
                            if metric.metricId.label=='throughputRead':
                                cls_backend_metric['throughputRead']= str2list(metric.values)               
                            if metric.metricId.label=='throughputWrite':
                                cls_backend_metric['throughputWrite']= str2list(metric.values)    
                            if metric.metricId.label=='latencyAvgRead':
                                cls_backend_metric['latencyAvgRead']= str2list(metric.values)  
                            if metric.metricId.label=='latencyAvgWrite':
                                cls_backend_metric['latencyAvgWrite']= str2list(metric.values)  
                            if metric.metricId.label=='congestion':
                                cls_backend_metric['congestion']= str2list(metric.values) 
                    # vsan_perf.append({"cls_backend_metric":cls_backend_metric})
                    vsan_perf["cls_backend_metric"]=cls_backend_metric

                    hosts_frontend_metric=[]
                    for host in hosts_uuid_map:
                        host_frontend_metric={}
                        host_frontend_metric['hostname']=host['hostname']
                        Spec.entityRefId = entityType[2]+":"+host['nodeUuid']
                        host_frontend_perf=vpm.QueryVsanPerf(querySpecs=[Spec],cluster=cls)
                        for item in host_frontend_perf:
                            host_frontend_metric['sampleInfo']=str2list(item.sampleInfo) 
                            for metric in item.value:
                                if metric.metricId.label=='iops':
                                    host_frontend_metric['iops']=str2list(metric.values) 
                                if metric.metricId.label=='throughput':
                                    host_frontend_metric['throughput']=str2list(metric.values)    
                                if metric.metricId.label=='latencyAvg':
                                    host_frontend_metric['latencyAvg']=str2list(metric.values) 
                                if metric.metricId.label=='latencyStddev':
                                    host_frontend_metric['latencyStddev']=str2list(metric.values) 
                                if metric.metricId.label=='ioCount':
                                    host_frontend_metric['ioCount']=str2list(metric.values) 
                                if metric.metricId.label=='congestion':
                                    host_frontend_metric['congestion']=str2list(metric.values)   
                                if metric.metricId.label=='iopsRead':
                                    host_frontend_metric['iopsRead']=str2list(metric.values) 
                                if metric.metricId.label=='throughputRead':
                                    host_frontend_metric['throughputRead']=str2list(metric.values) 
                                if metric.metricId.label=='latencyAvgRead':
                                    host_frontend_metric['readCount']=str2list(metric.values) 
                                if metric.metricId.label=='iopsWrite':
                                    host_frontend_metric['iopsWrite']=str2list(metric.values) 
                                if metric.metricId.label=='throughputWrite':
                                    host_frontend_metric['throughputWrite']=str2list(metric.values) 
                                if metric.metricId.label=='latencyAvgWrite':
                                    host_frontend_metric['latencyAvgWrite']=str2list(metric.values) 
                                if metric.metricId.label=='writeCount':
                                    host_frontend_metric['writeCount']=str2list(metric.values) 
                                if metric.metricId.label=='clientCacheHits':
                                    host_frontend_metric['clientCacheHits']=str2list(metric.values) 
                                if metric.metricId.label=='clientCacheHitRate':
                                    host_frontend_metric['clientCacheHitRate']=str2list(metric.values) 
                                if metric.metricId.label=='readCongestion':
                                    host_frontend_metric['readCongestion']=str2list(metric.values) 
                                if metric.metricId.label=='writeCongestion':
                                    host_frontend_metric['writeCongestion']=str2list(metric.values) 
                                if metric.metricId.label=='latencyMaxRead':
                                    host_frontend_metric['latencyMaxRead']=str2list(metric.values) 
                                if metric.metricId.label=='latencyMaxWrite':
                                    host_frontend_metric['latencyMaxWrite']=str2list(metric.values) 
                        hosts_frontend_metric.append(host_frontend_metric)
                    # vsan_perf.append({"hosts_frontend_metric":hosts_frontend_metric})
                    vsan_perf["hosts_frontend_metric"]=hosts_frontend_metric


                    hosts_backend_metric=[]
                    for host in hosts_uuid_map:
                        host_backend_metric={}
                        host_backend_metric['hostname']=host['hostname']
                        Spec.entityRefId = entityType[3]+":"+host['nodeUuid']
                        host_backend_perf=vpm.QueryVsanPerf(querySpecs=[Spec],cluster=cls)
                        for item in host_backend_perf:
                            host_backend_metric['sampleInfo']=str2list(item.sampleInfo) 
                            for metric in item.value:
                                if metric.metricId.label=='iops':
                                    host_backend_metric['iops']=str2list(metric.values) 
                                if metric.metricId.label=='throughput':
                                    host_backend_metric['throughput']=str2list(metric.values)    
                                if metric.metricId.label=='latencyAvg':
                                    host_backend_metric['latencyAvg']=str2list(metric.values) 
                                if metric.metricId.label=='latencyStddev':
                                    host_backend_metric['latencyStddev']=str2list(metric.values) 
                                if metric.metricId.label=='ioCount':
                                    host_backend_metric['ioCount']=str2list(metric.values) 
                                if metric.metricId.label=='congestion':
                                    host_backend_metric['congestion']=str2list(metric.values)     
                                if metric.metricId.label=='iopsRead':
                                    host_backend_metric['iopsRead']=str2list(metric.values) 
                                if metric.metricId.label=='throughputRead':
                                    host_backend_metric['throughputRead']=str2list(metric.values) 
                                if metric.metricId.label=='latencyAvgRead':
                                    host_backend_metric['readCount']=str2list(metric.values) 
                                if metric.metricId.label=='iopsWrite':
                                    host_backend_metric['iopsWrite']=str2list(metric.values) 
                                if metric.metricId.label=='throughputWrite':
                                    host_backend_metric['throughputWrite']=str2list(metric.values) 
                                if metric.metricId.label=='latencyAvgWrite':
                                    host_backend_metric['latencyAvgWrite']=str2list(metric.values) 
                                if metric.metricId.label=='writeCount':
                                    host_backend_metric['writeCount']=str2list(metric.values) 
                                if metric.metricId.label=='clientCacheHits':
                                    host_backend_metric['clientCacheHits']=str2list(metric.values) 
                                if metric.metricId.label=='clientCacheHitRate':
                                    host_backend_metric['clientCacheHitRate']=str2list(metric.values) 
                                if metric.metricId.label=='readCongestion':
                                    host_backend_metric['readCongestion']=str2list(metric.values) 
                                if metric.metricId.label=='writeCongestion':
                                    host_backend_metric['writeCongestion']=str2list(metric.values) 
                                if metric.metricId.label=='latencyMaxRead':
                                    host_backend_metric['latencyMaxRead']=str2list(metric.values) 
                                if metric.metricId.label=='latencyMaxWrite':
                                    host_backend_metric['latencyMaxWrite']=str2list(metric.values) 
                        hosts_backend_metric.append(host_backend_metric)
                    # vsan_perf.append({"hosts_backend_metric":hosts_backend_metric})
                    vsan_perf["hosts_backend_metric"]=hosts_backend_metric


                    cacheDisk_metric=[]           
                    Spec.entityRefId = entityType[4]+":*"
                    host_cacheDisk_perf=vpm.QueryVsanPerf(querySpecs=[Spec],cluster=cls)
                    # print(host_cacheDisk_perf)
                    for item in host_cacheDisk_perf:
                        host_cacheDisk_metric={}
                        host_cacheDisk_metric['sampleInfo']=str2list(item.sampleInfo) 
                        cachedisk_entityRefId=item.entityRefId.split(":")[1]  #'cache-disk:52c23c1b-c407-d9b3-2c5e-4b6540d2b15d'
                        for host in cluster_diskMapInfo:  #从cluster_diskMapInfo中找到cachedisk_entityRefId所属的主机
                            for map_info in host["hostDiskMapInfo"]:
                                for ssd_disk in map_info["ssdMapInfo"]:
                                    if ssd_disk["vsanUuid"]==cachedisk_entityRefId:
                                        host_cacheDisk_metric['hostname']=host["hostname"]
                        for metric in item.value:
                            if metric.metricId.label=='rcHitRate':
                                host_cacheDisk_metric['rcHitRate']=str2list(metric.values) 
                            if metric.metricId.label=='wbFreePct':
                                host_cacheDisk_metric['wbFreePct']=str2list(metric.values) 
                            if metric.metricId.label=='iopsRcRead':
                                host_cacheDisk_metric['iopsRcRead']=str2list(metric.values)  
                            if metric.metricId.label=='iopsRcWrite':
                                host_cacheDisk_metric['iopsRcWrite']=str2list(metric.values) 
                            if metric.metricId.label=='iopsWbRead':
                                host_cacheDisk_metric['iopsWbRead']=str2list(metric.values)     
                            if metric.metricId.label=='iopsWbWrite':
                                host_cacheDisk_metric['iopsWbWrite']=str2list(metric.values) 
                            if metric.metricId.label=='latencyWbRead':
                                host_cacheDisk_metric['latencyWbRead']=str2list(metric.values) 
                            if metric.metricId.label=='latencyWbWrite':
                                host_cacheDisk_metric['latencyWbWrite']=str2list(metric.values) 
                            if metric.metricId.label=='latencyRcRead':
                                host_cacheDisk_metric['latencyRcRead']=str2list(metric.values)                    
                            if metric.metricId.label=='latencyRcWrite':
                                host_cacheDisk_metric['latencyRcWrite']=str2list(metric.values) 
                            if metric.metricId.label=='checksumErrors':
                                host_cacheDisk_metric['checksumErrors']=str2list(metric.values) 
                            if metric.metricId.label=='latencyWbRead':
                                host_cacheDisk_metric['latencyWbRead']=str2list(metric.values) 
                        cacheDisk_metric.append(host_cacheDisk_metric)
                    vsan_perf["cacheDisk_metric"]=cacheDisk_metric

                    capacityDisk_metric=[]          
                    Spec.entityRefId = entityType[5]+":*"
                    host_capacityDisk_perf=vpm.QueryVsanPerf(querySpecs=[Spec],cluster=cls)        
                    for item in host_capacityDisk_perf:
                        host_capacityDisk_metric={}
                        host_capacityDisk_metric['sampleInfo']=str2list(item.sampleInfo) 
                        capacitydisk_entityRefId=item.entityRefId.split(":")[1]  #'cache-disk:52c23c1b-c407-d9b3-2c5e-4b6540d2b15d'
                        for host in cluster_diskMapInfo:  #从cluster_diskMapInfo中找到capacitydisk_entityRefId所属的主机
                            for map_info in host["hostDiskMapInfo"]:
                                for nossd_disk in  map_info["noSsdMapinfo"]:
                                    if nossd_disk["vsanUuid"]==capacitydisk_entityRefId:
                                        host_capacityDisk_metric['hostname']=host['hostname']  
                        for metric in item.value:
                            if metric.metricId.label=='iopsRead':
                                host_capacityDisk_metric['iopsRead']=str2list(metric.values) 
                            if metric.metricId.label=='latencyRead':
                                host_capacityDisk_metric['latencyRead']=str2list(metric.values)     
                            if metric.metricId.label=='iopsWrite':
                                host_capacityDisk_metric['iopsWrite']=str2list(metric.values) 
                            if metric.metricId.label=='latencyWrite':
                                host_capacityDisk_metric['latencyWrite']=str2list(metric.values) 
                            if metric.metricId.label=='capacityUsed':
                                host_capacityDisk_metric['capacityUsed']=str2list(metric.values) 
                            if metric.metricId.label=='checksumErrors':
                                host_capacityDisk_metric['checksumErrors']=str2list(metric.values)     
                        capacityDisk_metric.append(host_capacityDisk_metric) 
                    vsan_perf["capacityDisk_metric"]=capacityDisk_metric

                    hosts_pnicNet_metric=[]
                    for host in hosts_uuid_map:
                        host_pnicNet_metric={}
                        host_pnicNet_metric['hostname']=host['hostname']
                        Spec.entityRefId = entityType[9]+":"+host['nodeUuid']
                        host_pnicNet_perf=vpm.QueryVsanPerf(querySpecs=[Spec],cluster=cls)
                        for item in host_pnicNet_perf:
                            host_pnicNet_metric['sampleInfo']=str2list(item.sampleInfo) 
                            for metric in item.value:
                                if metric.metricId.label=='rxThroughput':
                                    host_pnicNet_metric['rxThroughput']=str2list(metric.values) 
                                if metric.metricId.label=='rxPacketsLossRate':
                                    host_pnicNet_metric['rxPacketsLossRate']=str2list(metric.values)     
                                if metric.metricId.label=='txThroughput':
                                    host_pnicNet_metric['txThroughput']=str2list(metric.values) 
                                if metric.metricId.label=='txPacketsLossRate':
                                    host_pnicNet_metric['txPacketsLossRate']=str2list(metric.values) 
                                if metric.metricId.label=='portRxDrops':
                                    host_pnicNet_metric['portRxDrops']=str2list(metric.values) 
                                if metric.metricId.label=='portTxDrops':
                                    host_pnicNet_metric['portTxDrops']=str2list(metric.values)     
                                if metric.metricId.label=='rxErr':
                                    host_pnicNet_metric['rxErr']=str2list(metric.values) 
                                if metric.metricId.label=='rxDrp':
                                    host_pnicNet_metric['rxDrp']=str2list(metric.values) 
                                if metric.metricId.label=='rxOvErr':
                                    host_pnicNet_metric['rxOvErr']=str2list(metric.values) 
                                if metric.metricId.label=='rxCrcErr':
                                    host_pnicNet_metric['rxCrcErr']=str2list(metric.values) 
                                if metric.metricId.label=='rxFrmErr':
                                    host_pnicNet_metric['rxFrmErr']=str2list(metric.values) 
                                if metric.metricId.label=='rxFifoErr':
                                    host_pnicNet_metric['rxFifoErr']=str2list(metric.values) 
                                if metric.metricId.label=='rxMissErr':
                                    host_pnicNet_metric['rxMissErr']=str2list(metric.values) 
                                if metric.metricId.label=='txErr':
                                    host_pnicNet_metric['txErr']=str2list(metric.values) 
                                if metric.metricId.label=='txDrp':
                                    host_pnicNet_metric['txDrp']=str2list(metric.values) 
                                if metric.metricId.label=='txAbortErr':
                                    host_pnicNet_metric['txAbortErr']=str2list(metric.values) 
                                if metric.metricId.label=='txCarErr':
                                    host_pnicNet_metric['txCarErr']=str2list(metric.values) 
                                if metric.metricId.label=='txFifoErr':
                                    host_pnicNet_metric['txFifoErr']=str2list(metric.values) 
                                if metric.metricId.label=='txHeartErr':
                                    host_pnicNet_metric['txHeartErr']=str2list(metric.values) 
                                if metric.metricId.label=='txWinErr':
                                    host_pnicNet_metric['txWinErr']=str2list(metric.values) 

                        hosts_pnicNet_metric.append(host_pnicNet_metric)
                    # vsan_perf.append({"hosts_pnicNet_metric":hosts_pnicNet_metric})
                    vsan_perf["hosts_pnicNet_metric"]=hosts_pnicNet_metric

                    hosts_cpu_metric=[]
                    for host in hosts_uuid_map:
                        host_cpu_metric={}
                        host_cpu_metric['hostname']=host['hostname']
                        Spec.entityRefId = entityType[10]+":"+host['nodeUuid']
                        host_cpu_perf=vpm.QueryVsanPerf(querySpecs=[Spec],cluster=cls)
                        for item in host_cpu_perf:
                            host_cpu_metric['sampleInfo']=str2list(item.sampleInfo) 
                            for metric in item.value:
                                if metric.metricId.label=='usedPct':
                                    host_cpu_metric['usedPct']=str2list(metric.values) 
                                if metric.metricId.label=='readyPct':
                                    host_cpu_metric['readyPct']=str2list(metric.values)     
                                if metric.metricId.label=='runPct':
                                    host_cpu_metric['runPct']=str2list(metric.values) 

                        hosts_cpu_metric.append(host_cpu_metric)
                    # vsan_perf.append({"hosts_cpu_metric":hosts_cpu_metric})
                    vsan_perf["hosts_cpu_metric"]=hosts_cpu_metric


                    hosts_memory_metric=[]
                    for host in hosts_uuid_map:
                        host_memory_metric={}
                        host_memory_metric['hostname']=host['hostname']
                        Spec.entityRefId = entityType[11]+":"+host['nodeUuid']
                        host_memory_perf=vpm.QueryVsanPerf(querySpecs=[Spec],cluster=cls)
                        for item in host_memory_perf:
                            kernelReservedSize=[]
                            uwReservedSize=[]
                            host_memory_metric['sampleInfo']=str2list(item.sampleInfo) 
                            for metric in item.value:
                                if metric.metricId.label=='kernelReservedSize':
                                    kernelReservedSize=str2list(metric.values) 
                                    kernelReservedSize=[Decimal(int(k)/1024/1024).quantize(Decimal("0")) for k in kernelReservedSize]
                                if metric.metricId.label=='uwReservedSize':
                                    uwReservedSize=str2list(metric.values)
                                    uwReservedSize=[Decimal(int(k)/1024/1024).quantize(Decimal("0")) for k in uwReservedSize]
                            host_memory_metric['vsanReservedSize']=[]
                            for i in range(len(kernelReservedSize)):
                                vsanReservedSize = kernelReservedSize[i]+uwReservedSize[i]
                                host_memory_metric['vsanReservedSize'].append(vsanReservedSize)

                        hosts_memory_metric.append(host_memory_metric)
                    # vsan_perf.append({"hosts_memory_metric":hosts_memory_metric})
                    vsan_perf["hosts_memory_metric"]=hosts_memory_metric

                    # vsan_info.append({"vsan_perf":vsan_perf})
                    vsan_info["vsan_perf"]=vsan_perf
                    cluster_config['vsan_enabled']=True
                    cluster_config['vsan_info']=vsan_info

                    sub_clusters.append(cluster_config)
                else:
                    sub_clusters.append(cluster_config)


        dc_config['name']=dc.name
        
        dc_config['clusters']=sub_clusters
        dc_config['dvs']=vdss
        dc_config['datastores']=datastores
        datacenters.append(dc_config)
    vcenter['datacenters']=datacenters
    vcenters=[]
    vcenters.append(vcenter)    

    
    print("write retrieved information abouts vsphere datacenter(s) in to json file {}".format(dc_json_file))
    with open(dc_json_file,'w') as f:
        json.dump(vcenters,f,indent=4,ensure_ascii=False,default=str,cls=MyEncoder)
        logger.info("DC信息写入文件："+dc_json_file)
    f.close  
    print("All datacenter(s) information are saved!")
    logger.info("the information acquisition of datacenter(s) is finished!")

if __name__=="__main__":
    # Check if the command-line arguments are provided
    if len(sys.argv) != 4:
        print("Usage: "+ os.path.basename(__file__)+" <vchost> <vcuser> <vcpassword>")
        sys.exit(1)

    # Retrieve the arguments
    vchost = sys.argv[1]
    vcuser = sys.argv[2]
    vcpassword = sys.argv[3]

    # print(sys.argv)


    QueryDCsInfo(vchost=vchost,vcuser=vcuser,vcpassword=vcpassword)