from decimal import Decimal
import datetime
import pytz
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
import atexit
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import json
import os
import logging
import ssl
import sys



def establish_connection(vchost,vcuser,vcpassword):
    try:
        si = SmartConnect(host=vchost, user=vcuser, pwd=vcpassword, sslContext=s)
        atexit.register(Disconnect, si)
        return si
    except Exception as e:
        print(f"Failed to connect to vCenter at {vchost}: {e}")
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
        portgroup_info = dict()
        portgroup_info.update(
            {'name': portgroup.spec.name, 'vlanId': portgroup.spec.vlanId,
             'vswitchName': portgroup.spec.vswitchName,
             'nicTeamingPolicy': portgroup.spec.policy.nicTeaming.policy,
             'allowPromiscuous': portgroup.spec.policy.security.allowPromiscuous,
             'macChanges': portgroup.spec.policy.security.macChanges,
             'forgedTransmits': portgroup.spec.policy.security.forgedTransmits})
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
   host_datetime_info={}
#    host_datetime_info['enabled']=host.config.dateTimeInfo.enabled
#    host_datetime_info['lastSyncTime']=host.config.dateTimeInfo.lastSyncTime
   host_datetime_info['ntpServer']=host.config.dateTimeInfo.ntpConfig.server  #server[]
   return host_datetime_info

def buildQuery(content, vchtime, counterIds, instance, obj):
    perfManager = content.perfManager
    if instance=="" or instance is None:
         instance="*"
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
        exit()



def get_all_objs(content, vimtype):
    obj = []
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for managed_object_ref in container.view:
        # obj.update({managed_object_ref: managed_object_ref.name})
        obj.append(managed_object_ref)
    return obj

def QueryHostsInfo(si):
    content=si.content
    hosts=[]

    print("Gathering ESXi Hosts information")
    logging.info("开始esxi主机信息收集")
    allHosts=get_all_objs(content,[vim.HostSystem])
    for host in allHosts:
        logger.info("开始收集esxi主机信息："+ host.name)
        host_dict={}
        host_BASIC=[]
        host_BIOSINFO=[]
        # host_CERTIFICATE=[]
        host_CPU_RAM_CONFIG=[]
        host_CPU_RAM_USAGE=[]
        host_STORAGE_DS=[]
        host_STORAGE_MULTIPATH=[]
        host_STORAGE_HBA=[]
        host_STORAGE_LUN=[]
        # host_VSWITCH=[]
        host_PNIC=[]
        # host_VNIC=[]

        print(host.name)

        timezones=host.configManager.dateTimeSystem.QueryAvailableTimeZones()
        host_dict['timezone']=timezones[0].name
        host_datetime=host.configManager.dateTimeSystem.QueryDateTime()
        deviation=abs(datetime.datetime.now(pytz.utc)-host_datetime.replace(tzinfo=pytz.utc)).total_seconds()
        host_dict['deviation']=Decimal(deviation).quantize(Decimal("0"))

        host_dict['host']=host.summary.config.name
        #获取证书
        pem=""
        for byte in host.config.certificate:
            pem=pem+chr(byte)
        cert=x509.load_pem_x509_certificate(pem.encode(), default_backend())
        #  print('Valid from ' + str(cert.not_valid_before) + ' to ' + str(cert.not_valid_after))
        cert_info = host.configManager.certificateManager.certificateInfo
        #    print(type(cert.not_valid_after))  
        #    if abs((cert_info.notAfter.date()-datetime.date.today()).days)>180:
        #        print(" Certificate Subject:"+cert_info.subject+' Valid from ' + str(cert_info.notBefore) + ' to ' + str(cert_info.notAfter))
        #     #    print(abs((cert_info.notAfter.date()-datetime.date.today()).days))
        
        cert={}
        cert['subject']=cert_info.subject
        cert['sign_date']=cert_info.notBefore.strftime('%Y-%m-%d %H:%M:%S')
        cert['expired_date']=cert_info.notAfter.strftime('%Y-%m-%d %H:%M:%S')

        host_dict['certificate']=cert

            #获取NTP
        host_dict['datetime_info']=get_host_datetime(host)
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
        numVms=len(host.vm)
        
        numPoweron=0
        numvCPUs=0
        for i in range(numVms):
            
            if host.vm[i].runtime.powerState=="poweredOn":
                numPoweron+=1
                numvCPUs+=host.vm[i].summary.config.numCpu

        host_dict['numVms']=numVms
        host_dict['numPoweronVMs']=numPoweron
        host_dict['numvCPUs']=numvCPUs

        #    print("numPoweron/numVms:"+str(numPoweron)+"/"+str(numVms)) 
        host_basic_info={}
        #    host_basic_info['host']=host.summary.config.name
        host_basic_info['mgmtIP']=host.summary.managementServerIp
        host_basic_info['vendor']=host.summary.hardware.vendor
        host_basic_info['model']=host.summary.hardware.model
        host_basic_info['sn']=host.hardware.systemInfo.serialNumber
        host_basic_info['biosInfo']=host.hardware.biosInfo.biosVersion+"|"+str(host.hardware.biosInfo.releaseDate)
        host_basic_info['esxi']=host.config.product.fullName
        host_basic_info['uptime']=Decimal(host.summary.quickStats.uptime/3600).quantize(Decimal("0.0"))
        host_BASIC.append(host_basic_info)
        host_dict['basic_info']=host_BASIC

        host_bios_info={}
        #    host_bios_info['host']=host.summary.config.name
        host_bios_info['biosVersion']=host.hardware.biosInfo.biosVersion
        host_bios_info['releaseDate']=str(host.hardware.biosInfo.releaseDate.strftime("%m/%d/%Y"))
        host_bios_info['firmwareMajorRelease']=host.hardware.biosInfo.firmwareMajorRelease
        host_bios_info['firmwareMinorRelease']=host.hardware.biosInfo.firmwareMinorRelease
        #    host_bios_info['majorRelease']=host.hardware.biosInfo.majorRelease
        #    host_bios_info['minorRelease']=host.hardware.biosInfo.minorRelease
        host_BIOSINFO.append(host_bios_info)
        host_dict['bios_info']=host_BIOSINFO
        #    print(host_bios_info)
        


        
        
        cpu_ram_config={}
        #    cpu_ram_config['host']=host.summary.config.name
        cpu_ram_config['cpuModel']=host.summary.hardware.cpuModel
        cpu_ram_config['cpuMhz']=host.summary.hardware.cpuMhz
        cpu_ram_config['numCpuCores']=host.summary.hardware.numCpuCores
        cpu_ram_config['numCpuThreads']=host.summary.hardware.numCpuThreads
        cpu_ram_config['ramSize']=Decimal(host.summary.hardware.memorySize/1024/1024/1024).quantize(Decimal("0.0"))
        host_CPU_RAM_CONFIG.append(cpu_ram_config)
        host_dict['cpu_ram_config']=host_CPU_RAM_CONFIG


        
        cpu_ram_usage={}
        #    cpu_ram_usage['host']=host.summary.config.name
        cpu_ram_usage['consolidate_ratio']=Decimal(numvCPUs/host.summary.hardware.numCpuCores).quantize(Decimal("0.0"))
        cpu_ram_usage['cpu_usage']=Decimal(host.summary.quickStats.overallCpuUsage/host.summary.hardware.cpuMhz/host.summary.hardware.numCpuCores).quantize(Decimal("0.000"))
        cpu_ram_usage['ram_usage']=Decimal(host.summary.quickStats.overallMemoryUsage*1024*1024/host.summary.hardware.memorySize).quantize(Decimal("0.000"))
        #    print(cpu_ram_usage)

        host_CPU_RAM_USAGE.append(cpu_ram_usage)
        host_dict['cpu_ram_usage']=host_CPU_RAM_USAGE

        


        for ds in host.datastore:
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
        host_dict['datastores']=host_STORAGE_DS


        #    print("esxi version:"+host.config.product.fullName)
        #    print("esxi build:"+host.config.product.build)
        #    print("esxi patchLevel:"+host.config.product.patchLevel)
        #    print("esxi licenseProductName:"+host.config.product.licenseProductName)
        #    print("esxi licenseProductVersion:"+host.config.product.licenseProductVersion)

        
        if len(host.config.storageDevice.hostBusAdapter)>0:
            for adpt in host.config.storageDevice.hostBusAdapter:
                hba={}
                #  print("hba device:"+adpt.device+" hba model:"+adpt.model+" driver:"+adpt.driver+" storage protocol:"+adpt.storageProtocol)
                #  hba['host']=host.summary.config.name
                hba['name']=adpt.device
                hba['model']=adpt.model
                hba['driver']=adpt.driver
                hba['protocol']=adpt.storageProtocol
                host_STORAGE_HBA.append(hba)
        host_dict['hbas']=host_STORAGE_HBA
        
        
        if len(host.config.storageDevice.scsiLun)>0:
            for scsi_lun in host.config.storageDevice.scsiLun:
                scsilun={}
                # print("display name:"+scsi_lun.displayName+" lunType:"+scsi_lun.lunType+" model:"+scsi_lun.model)
                # scsilun['host']=host.summary.config.name
                scsilun['displayName']=scsi_lun.displayName
                scsilun['lunType']=scsi_lun.lunType
                scsilun['model']=scsi_lun.model
                host_STORAGE_LUN.append(scsilun)
        host_dict['scsi_lun']=host_STORAGE_LUN   


        
        for path in host.config.multipathState.path:
            multipath={}
            #   print("path name:"+path.name +" path state:"+path.pathState)
            #   multipath['host']=host.summary.config.name
            multipath['path name']=path.name
            multipath['path state']=path.pathState
            host_STORAGE_MULTIPATH.append(multipath)
        host_dict['multipaths']=host_STORAGE_MULTIPATH
        
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
        # host_dict['vswitches']=host_VSWITCH
        host_dict['vswitches']=get_host_vswitches(host)

        for pnic in host.config.network.pnic:
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
        host_dict['pnics']=host_PNIC       
            


        
        # for vnic in host.config.network.vnic:
        #      v_nic={}
        #  #   print(vnic)
        #      # print("key:"+vnic.key+" device:"+vnic.device+" \
        #      #             IP:"+vnic.spec.ip.ipAddress+" Mask:"+vnic.spec.ip.subnetMask+" \
        #      #                 mac:"+vnic.spec.mac+" MTU:"+str(vnic.spec.mtu)) 
        #      # v_nic['host']=host.summary.config.name
        #      v_nic['name']=vnic.device
        #      v_nic['mac']=vnic.spec.mac
        #      v_nic['IP']=vnic.spec.ip.ipAddress
        #      v_nic['submask']=vnic.spec.ip.subnetMask
        #      v_nic['mtu']=vnic.spec.mtu
        #      # print(v_nic)
        #      host_VNIC.append(v_nic)  
        host_dict['vnics']=get_host_vnics(host)

        
        
        CPU_disk_metrics_dict={}
        network_metrics_dict={}
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

            #counter_id 150 network performace counter
        counter_ids=[150]
        instance=""


            # # Query the performance manager
            # # based on the metrics created above    
        result_stats=buildQuery(content, vchtime, counter_ids,instance,host)
        
        for instance_metric in result_stats:
                values=instance_metric.value
                for v in values:
                    network_metric={}

                    network_metric["counterId"]=v.id.counterId
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
        host_dict['network_metrics']=network_metrics
        


        counter_ids=[6,12,140] 
        instance=""  
        result_stats=buildQuery(content, vchtime, counter_ids,instance,host)
            # print(result_stats)
        for instance_metric in result_stats:
                values=instance_metric.value
                for v in values:
                    metric={}                
                    if v.id.instance=="":
                        metric["endTime"]=vchtime.astimezone()
                        metric["counterId"]=v.id.counterId
                        if v.id.counterId==6:
                            metric["value"]=[Decimal(value*100/(host.summary.hardware.numCpuCores*host.summary.hardware.cpuMhz)).quantize(Decimal(0.00)) for value in v.value]
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
        host_dict['CPU_disk_metrics']=CPU_disk_metrics

        hosts.append(host_dict)
    # return hosts
   

       
    
    
    with open(hosts_json_file,'w') as f:
        json.dump(hosts,f,indent=4,ensure_ascii=False,default=str,cls=MyEncoder)
        logger.info("收集的主机信息写入文件："+hosts_json_file)
    f.close
    print("All hosts information are saved!")
    logger.info("the information acquisition of ESXi host(s) is finished!")

if __name__=="__main__":
    # Check if the command-line arguments are provided
    if len(sys.argv) != 4:
        print("Usage: "+ os.path.basename(__file__)+" <vchost> <vcuser> <vcpassword>")
        sys.exit(1)

    # Retrieve the arguments
    vchost = sys.argv[1]
    vcuser = sys.argv[2]
    vcpassword = sys.argv[3]

    cwd = os.getcwd()
    current_time=datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    hosts_json_file=os.path.join(cwd,'data',"hosts-"+current_time+".json") 
    logfile_path=os.path.join(cwd,'data','log',"hostsInfo_gathering.log")
    log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
    logger=logging.getLogger('hosts_logger')
    fh=logging.FileHandler(filename=logfile_path,mode='a')
    fh.setLevel(logging.INFO)
    fh.setFormatter(log_formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)

    s = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    s.verify_mode = ssl.CERT_NONE

    si=establish_connection(vchost,vcuser,vcpassword)
    QueryHostsInfo(si)

