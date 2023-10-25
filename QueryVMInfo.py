from decimal import Decimal
import datetime
import os
from pyVmomi import vim
import re
import json
import logging
from pyVim.connect import SmartConnect, Disconnect
import atexit
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

def get_all_objs(content, vimtype):
    obj = []
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for managed_object_ref in container.view:
        # obj.update({managed_object_ref: managed_object_ref.name})
        obj.append(managed_object_ref)
    return obj

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

def get_vm_disk_info(vm):
    disks=[]
    for file in vm.layoutEx.file:
            disk={}
            if file.type=="diskDescriptor":
                #从路径获取磁盘文件名
                shortname=file.name.split("/")[-1]
                # print("file name:"+shortname)
                # print("file size:"+str(file.size))
                rx=re.search('(.*)-(000\d\d\d\.vmdk)', shortname)
                if  rx is None:
                    # disk['backingObjectId']=file.backingObjectId
                    disk['disk_name']=shortname
                    disk['disk_path']=file.name
                    disk['used_disk_size']=file.size
                    disk['disk_snap_num']=0
                    disk['disk_snap_size']=0
                    disks.append(disk)

                else:
                    for i in range(len(disks)):
                        if disks[i]['disk_name']==rx.group(1)+".vmdk":
                            disks[i]['used_disk_size']+=file.size
                            disks[i]['disk_snap_num']+=1
                            disks[i]['disk_snap_size']+=file.size
    
    i=0
    for dev in vm.config.hardware.device:
        if type(dev).__name__ == 'vim.vm.device.VirtualDisk':
            disks[i]['provisioned_disk_size']=dev.capacityInBytes
            i=i+1
    
    return disks        

def get_vm_snap_createtime(vm_rootSnapList:list,vm_snap_create_list=[]) ->list: 
    """
    :param vm_rootSnapList: the list of the VM's root snapshot
    :return vm_snap_create_list: return a list consists of every snapshot's creation time.
    """   
    # vm_snap_create_list=[]
    if len(vm_rootSnapList)>0:
        for i in range(len(vm_rootSnapList)):
          vm_snap_create_list.append(vm_rootSnapList[i].createTime.strftime("%m/%d/%Y, %H:%M:%S"))
          if  len(vm_rootSnapList[i].childSnapshotList)>0:      
            get_vm_snap_createtime(vm_rootSnapList[i].childSnapshotList,vm_snap_create_list)
    return vm_snap_create_list  
    # print(vm_snap_create_list)
    
#Capture VM's nics
def get_vm_nics(vm,content):
   """    :param vm: the VM object
   """   
   vm_nics=[]

   for dev in vm.config.hardware.device:
        vm_nic={}
        if isinstance(dev, vim.vm.device.VirtualEthernetCard):
            dev_backing = dev.backing
            port_group = None
            vlan_id = None
            v_switch = None
            
            if hasattr(dev_backing, 'port'):
                port_group_key = dev.backing.port.portgroupKey
                dvs_uuid = dev.backing.port.switchUuid
                try:
                    dvs = content.dvSwitchManager.QueryDvsByUuid(dvs_uuid)
                except Exception:
                    port_group = "** Error: DVS not found **"
                    vlan_id = "NA"
                    v_switch = "NA"
                else:
                    pg_obj = dvs.LookupDvPortGroup(port_group_key)
                    port_group = pg_obj.config.name
                    vlan_id = pg_obj.config.defaultPortConfig.vlan.vlanId
                    v_switch = str(dvs.name)
                    connected=dev.connectable.connected
            else:
                port_group = dev.backing.network.name                
                vm_host = vm.runtime.host                

                pgs = get_host_portgroups(vm_host)
                for p in pgs:
                    if port_group in p.values():
                        vlan_id = p["vlanId"]
                        v_switch = str(p["vswitchName"])
            if port_group is None:
                port_group = 'NA'
            if vlan_id is None:
                vlan_id = 'NA'
            if v_switch is None:
                v_switch = 'NA'

            vm_nic['name']=dev.deviceInfo.label
            vm_nic['macAddress']=dev.macAddress
            vm_nic['vSwitch_name']=v_switch
            vm_nic['portGroup']=port_group
            if isinstance(vlan_id,int) or isinstance(vlan_id,str):
                vm_nic['VLANID']=vlan_id
            else:
                vm_nic['VLANID']=str(vlan_id[0].start)+"-"+str(vlan_id[0].end)              
            vm_nic['connected']=dev.connectable.connected
            vm_nics.append(vm_nic)
   return vm_nics

def esxi_vmtools_version_mapping_load(filepath):
    mapping_lines=[]
    with open(filepath,'r') as f:
        lines=f.readlines()
    f.close

    for line in lines:
        rx=re.search(r'^#',line)
        if not rx:
            mapping_lines.append(line)
    return mapping_lines

def vmtools_status_check(vm):
    if vm.guest.toolsVersionStatus2=='guestToolsSupportedOld':
        return "Old"
    if vm.guest.toolsVersionStatus2=='guestToolsCurrent':
        return "Current"
    if vm.guest.toolsVersionStatus2=='guestToolsUnmanaged':
        return "Unmanaged"
    if vm.guest.toolsVersionStatus2=='guestToolsNotInstalled':
        return "NotInstalled"
    
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

def QueryVMsInfo(si):
    
    logger.info("The information acquisition of virtual machine(s) is started!")
    vmlist=[]
    content=si.content
    

    getallvms=get_all_objs(content,[vim.VirtualMachine])
    for vm in getallvms:
        logger.info('收集虚拟机信息：'+vm.config.name)
        vm_info={}

        #列出VM所在的datastores
        datastores=[]
        for ds in vm.config.datastoreUrl:
            datastores.append(ds.name)

        vm_nics=get_vm_nics(vm,content=content)

        if vm.runtime.bootTime is not None:
            boot_time=vm.runtime.bootTime.strftime("%m/%d/%Y, %H:%M:%S")
        else:
            boot_time=""

        
        snap_createTime=[]
        oldest_snap_createTime=""
        if hasattr(vm.snapshot,"rootSnapshotList"):
                snap_createTime=get_vm_snap_createtime(vm.snapshot.rootSnapshotList,vm_snap_create_list=[])
                oldest_snap_createTime=snap_createTime[0]
        else: 
            snap_createTime=[]
            oldest_snap_createTime=""
        #    print("no snapshot")

        # vm_rootSnapList=vm.snapshot.rootSnapshotList
        # if len(vm.snapshot.rootSnapshotList)>0:
        #   vm_snap_create_list.append(vm_rootSnapList[0].createTime.strftime("%m/%d/%Y, %H:%M:%S"))
        #   if  len(vm_rootSnapList[0].childSnapshotList)>0:  
        #     print(vm_rootSnapList[0].childSnapshotList)   
        #     get_vm_root_snap_createtime(vm_rootSnapList[0].childSnapshotList)   


        # provisioned_total_size=0
        # for dev in vm.config.hardware.device:
        #    if type(dev).__name__ == 'vim.vm.device.VirtualDisk':
        #     provisioned_total_size+=dev.capacityInKB
        # print(str(round(provisioned_total_size/1024/1024,1))+"GB")

        vm_disk_info=get_vm_disk_info(vm)

        vm_perf_metrics={}
        vm_perf_metrics=[]
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
    #         # # Using the IDs form a list of MetricId
    #         # # objects for building the Query Spec
    #         # 2:'CPU usage as a percentage during the interval'
    #         # 6:' usagemhz CPU usage in megahertz during the interval'
    #         # 12: ready Time that the virtual machine was ready, but could not get scheduled to run on the physical CPU during last measurement interval
    #         # 140:maxTotalLatency 'Highest latency value across all disks used by the host'
        #counter_id 150 network performace counter
        counter_ids=[6,12,140] 
        instance=""


        # # Query the performance manager
        # # based on the metrics created above
        # 
        if vm.runtime.powerState=="poweredOn":    
            result_stats=buildQuery(content, vchtime, counter_ids,instance,vm)
            # print(result_stats)
            for instance_metric in result_stats:
                values=instance_metric.value
                for v in values:
                    if v.id.instance=="":
                        metric={}
                        metric["counterId"]=v.id.counterId
                        if v.id.counterId==6:
                            metric["value"]=[ Decimal(value*100/(vm.runtime.host.summary.hardware.cpuMhz*vm.config.hardware.numCPU)).quantize(Decimal('0.00')) for value in v.value]  #vm.runtime.host.summary.hardware.cpuMhz* Decimal().quantize(Decimal("0.0"))
                        elif v.id.counterId==12:
                            metric["value"]=[Decimal(value*100/(20*1000)).quantize(Decimal('0.00')) for value in v.value]
                        else:
                            metric["value"]=[value for value in v.value]                                        
                        metric_time=[]
                        endTime = vchtime.astimezone() - datetime.timedelta(minutes=1)
                        for i in range(len(metric["value"])):
                            metric_time.append((endTime-datetime.timedelta(seconds=i*20)).strftime("%m/%d/%Y %H:%M:%S"))

                        metric_time.reverse()
                        metric["endTime"]=metric_time
                        vm_perf_metrics.append(metric)

        # vm_perf_metric[]={}



        vmindex=[
            'Display_name',
            'DNS_name',
            'powerState',
            'isTemplate',
            'isSyncTimeWithHost',
            'toolsVersion',
            'tools_status',
            'createDate',
            #  vm.config.files,
            'config_guestFullName',
            'VMwareTools_guestFullName',
            'numCPU',
            'numCoresPerSocket',
            'cpuHotAddEnabled',
            'memoryMB',
            'memoryHotAddEnabled',
            'disks_info',
            'uuid',
            'hardwareVersion',
            'datastores',
            'vmPath',
            'bootOrder',
            'bootDelay',
            'firmware',       
            'bootTime',
            'consolidationNeeded',
            'guestState',       
            'guestHeartbeatStatus',
            'esxihostname',
            'vnics',
            'guest_ipAddress',
            'Snapshot_num',
            'oldest_snap_createTime',
            'vm_perf_metric'       
            ]

        vmvalue=[
            vm.config.name,
            vm.guest.hostName,
            vm.runtime.powerState,
            vm.config.template,
            vm.config.tools.syncTimeWithHost,
            vm.config.tools.toolsVersion,
            vmtools_status_check(vm),
            vm.config.createDate.strftime("%m/%d/%Y, %H:%M:%S"),
            #  vm.config.files,
            vm.config.guestFullName,
            vm.guest.guestFullName,
            vm.config.hardware.numCPU,
            vm.config.hardware.numCoresPerSocket,
            vm.config.cpuHotAddEnabled,
            vm.config.hardware.memoryMB,
            vm.config.memoryHotAddEnabled,
            vm_disk_info,#[]
            vm.config.uuid,
            vm.config.version,
            datastores, #[]
            vm.summary.config.vmPathName,
            vm.config.bootOptions.bootOrder, #[]
            vm.config.bootOptions.bootDelay,
            vm.config.firmware,       
            boot_time,
            vm.runtime.consolidationNeeded,
            vm.guest.guestState,       
            vm.guestHeartbeatStatus,
            vm.runtime.host.name,
            vm_nics, #[]
            vm.guest.ipAddress,
            len(snap_createTime),
            oldest_snap_createTime,
            vm_perf_metrics,       
            ]

        for i in range(len(vmvalue)):
            vm_info[vmindex[i]]=vmvalue[i]
        vmlist.append(vm_info)
    

    
    with open(vm_json_file,'w') as f:
        json.dump(vmlist,f,indent=4,ensure_ascii=False,default=str,cls=MyEncoder)
        logger.info("收集的虚拟机信息写入文件："+vm_json_file)
    f.close
    logger.info("the information acquisition of virtual machine(s) is finished!")

if __name__=="__main__":
    # Check if the command-line arguments are provided
    if len(sys.argv) != 4:
        print("Usage: "+ os.path.basename(__file__)+" <vchost> <vcuser> <vcpassword>")
        sys.exit(1)

    # Retrieve the arguments
    vchost = sys.argv[1]
    vcuser = sys.argv[2]
    vcpassword = sys.argv[3]

    s = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    s.verify_mode = ssl.CERT_NONE
    cwd = os.getcwd()
    current_time=datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    vm_json_file=os.path.join(cwd,'data',"vms-"+current_time+".json")

    logfile_path=os.path.join(cwd,'data','log',"vmsInfo_gathering.log")
    log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
    logger=logging.getLogger('vms_logger')
    fh=logging.FileHandler(filename=logfile_path,mode='a')
    fh.setLevel(logging.INFO)
    fh.setFormatter(log_formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)

    si=establish_connection(vchost=vchost,vcuser=vcuser,vcpassword=vcpassword)
    QueryVMsInfo(si)
