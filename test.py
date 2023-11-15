
from pyVim.connect import SmartConnectNoSSL, Disconnect
from pyVmomi import vim
from datetime import timedelta
import atexit
import os 
import json
import re
import logging
import datetime
import paramiko
import sys
import time
import socket
 
data_dir=os.path.join(os.getcwd(),'data')

def file_search(dir,prefix,surfix):
  find_flag=False
  files=os.listdir(dir)
  for file in files:
    if file.startswith(prefix) and file.endswith(surfix):
      find_flag=True
      return os.path.join(dir,file)
  if not find_flag:
    return find_flag

def connect_vc(host, user, pwd, port):
    si = SmartConnectNoSSL(host=host, user=user, pwd=pwd, port=port)
 
    # disconnect this thing
    atexit.register(Disconnect, si)
    return si
 
 
# def build_query(content, vc_time, counter_id, obj, interval):
#     metric_id = vim.PerformanceManager.MetricId(counterId=counter_id, instance="")
#     start_time = vc_time - timedelta(minutes=(interval + 1))
#     end_time = vc_time - timedelta(minutes=1)
#     query = vim.PerformanceManager.QuerySpec(intervalId=20,
#                                              entity=obj,
#                                              metricId=[metric_id],
#                                              startTime=start_time,
#                                              endTime=end_time)
#     perf_results = content.perfManager.QueryPerf(querySpec=[query])
#     if perf_results:
#         return perf_results
#     else:
#         pass
 
 
# def print_statistics(obj, content, vc_time, interval, perf_dict, ):
#     stat_interval = interval * 3  # There are 3per 20s samples in each minute
 
#     # Network usage (Tx/Rx)
#     # statNetworkTx = BuildQuery(content, vchtime, (stat_check(perf_dict, 'net.usage.maximum')), obj, interval)
#     # networkTx = (float(sum(statNetworkTx[0].value[0].value) * 8 / 1024) / statInt)
#     # statNetworkRx = BuildQuery(content, vchtime, (stat_check(perf_dict, 'net.usage.minimum')), obj, interval)
#     # networkRx = (float(sum(statNetworkRx[0].value[0].value) * 8 / 1024) / statInt)
 
#     # Network utilization (combined transmit-rates and receive-rates) during the interval = 145
#     network_usage = build_query(content, vc_time, stat_check(perf_dict, 'net.usage.average'), obj, interval)
#     try:
#         print('statNetworkThroughput:%sMB' % (round((((sum(network_usage[0].value[0].value)) / 1024) / stat_interval), 2)))
 
#     except TypeError:
#         # 关机的ESXi主机无法获取到数据
#         pass
 
 
# def stat_check(perf_dict, counter_name):
#     """通过performance counter名称获取counter id"""
#     counter_id = perf_dict[counter_name]
#     return counter_id
 
 
# def main():
#     username = 'administrator@vsphere.local'
#     # password = 'eRB$i5PUl@20211101'
#     # vc_ip = '192.168.83.212'
#     password = '123Qwe,.'
#     vc_ip = '192.168.10.82'
#     vc_port = '443'
#     statistics_interval_time = 10   # 分钟为单位
#     si = connect_vc(host=vc_ip, user=username, pwd=password, port=vc_port)
#     content = si.RetrieveContent()
 
#     # Get vCenter date and time for use as baseline when querying for counters
#     vc_time = si.CurrentTime()
 
#     # 获取所有performance counter，并放入字典中
#     perf_dict = {}
#     perf_list = content.perfManager.perfCounter
#     for counter in perf_list:
#         counter_full = "{}.{}.{}".format(counter.groupInfo.key, counter.nameInfo.key, counter.rollupType)
#         perf_dict[counter_full] = counter.key # perf_dict包含了所有的perfCounter
#     print(perf_dict)
#     # 获取ESXi主机对象
#     container_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
 
#     for obj in container_view.view:
#         print_statistics(obj, content, vc_time, statistics_interval_time, perf_dict)
 
 
# # Start program
# if __name__ == "__main__":
#     main()





"""
Python program that generates various statistics for one or more virtual machines
A list of virtual machines can be provided as a comma separated list.
"""
 
# from __future__ import print_function
# from pyVim.connect import SmartConnectNoSSL, Disconnect
# from pyVmomi import vmodl, vim
# from datetime import timedelta, datetime
# import atexit
 
 
# def connect_vc(host, user, pwd, port):
#     si = SmartConnectNoSSL(host=host, user=user, pwd=pwd, port=port)
 
#     # disconnect this thing
#     atexit.register(Disconnect, si)
#     return si
 
 
# def BuildQuery(content, vchtime, counterId, instance, vm, interval):
#     perfManager = content.perfManager
#     metricId = vim.PerformanceManager.MetricId(counterId=counterId, instance=instance)
#     startTime = vchtime - timedelta(minutes=(interval + 1))
#     endTime = vchtime - timedelta(minutes=1)
#     query = vim.PerformanceManager.QuerySpec(intervalId=20, entity=vm, metricId=[metricId], startTime=startTime,
#                                              endTime=endTime)
#     perfResults = perfManager.QueryPerf(querySpec=[query])
#     if perfResults:
#         return perfResults
#     else:
#         print('ERROR: Performance results empty.  TIP: Check time drift on source and vCenter server')
#         print('Troubleshooting info:')
#         print('vCenter/host date and time: {}'.format(vchtime))
#         print('Start perf counter time   :  {}'.format(startTime))
#         print('End perf counter time     :  {}'.format(endTime))
#         print(query)
#         exit()
 
 
 
# def PrintVmInfo(vm, content, vchtime, interval, perf_dict, ):
#     statInt = interval * 3  # There are 3 20s samples in each minute
#     summary = vm.summary
#     disk_list = []
#     network_list = []
 
#     # Convert limit and reservation values from -1 to None
#     if vm.resourceConfig.cpuAllocation.limit == -1:
#         vmcpulimit = "None"
#     else:
#         vmcpulimit = "{} Mhz".format(vm.resourceConfig.cpuAllocation.limit)
#     if vm.resourceConfig.memoryAllocation.limit == -1:
#         vmmemlimit = "None"
#     else:
#         vmmemlimit = "{} MB".format(vm.resourceConfig.cpuAllocation.limit)
 
#     if vm.resourceConfig.cpuAllocation.reservation == 0:
#         vmcpures = "None"
#     else:
#         vmcpures = "{} Mhz".format(vm.resourceConfig.cpuAllocation.reservation)
#     if vm.resourceConfig.memoryAllocation.reservation == 0:
#         vmmemres = "None"
#     else:
#         vmmemres = "{} MB".format(vm.resourceConfig.memoryAllocation.reservation)
 
#     vm_hardware = vm.config.hardware
#     for each_vm_hardware in vm_hardware.device:
#         if (each_vm_hardware.key >= 2000) and (each_vm_hardware.key < 3000):
#             disk_list.append('{} | {:.1f}GB | Thin: {} | {}'.format(each_vm_hardware.deviceInfo.label,
#                                                          each_vm_hardware.capacityInKB/1024/1024,
#                                                          each_vm_hardware.backing.thinProvisioned,
#                                                          each_vm_hardware.backing.fileName))
#         elif (each_vm_hardware.key >= 4000) and (each_vm_hardware.key < 5000):
#             network_list.append('{} | {} | {}'.format(each_vm_hardware.deviceInfo.label,
#                                                          each_vm_hardware.deviceInfo.summary,
#                                                          each_vm_hardware.macAddress))
 
#     #CPU Ready Average
#     statCpuReady = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'cpu.ready.summation')), "", vm, interval)
#     cpuReady = (float(sum(statCpuReady[0].value[0].value)) / statInt)
#     #CPU Usage Average % - NOTE: values are type LONG so needs divided by 100 for percentage
#     statCpuUsage = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'cpu.usage.average')), "", vm, interval)
#     cpuUsage = ((float(sum(statCpuUsage[0].value[0].value)) / statInt) / 100)
#     #Memory Active Average MB
#     statMemoryActive = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'mem.active.average')), "", vm, interval)
#     memoryActive = (float(sum(statMemoryActive[0].value[0].value) / 1024) / statInt)
#     #Memory Shared
#     statMemoryShared = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'mem.shared.average')), "", vm, interval)
#     memoryShared = (float(sum(statMemoryShared[0].value[0].value) / 1024) / statInt)
#     #Memory Balloon
#     statMemoryBalloon = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'mem.vmmemctl.average')), "", vm, interval)
#     memoryBalloon = (float(sum(statMemoryBalloon[0].value[0].value) / 1024) / statInt)
#     #Memory Swapped
#     statMemorySwapped = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'mem.swapped.average')), "", vm, interval)
#     memorySwapped = (float(sum(statMemorySwapped[0].value[0].value) / 1024) / statInt)
#     #Datastore Average IO
#     statDatastoreIoRead = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'datastore.numberReadAveraged.average')),
#                                      "*", vm, interval)
#     DatastoreIoRead = (float(sum(statDatastoreIoRead[0].value[0].value)) / statInt)
#     statDatastoreIoWrite = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'datastore.numberWriteAveraged.average')),
#                                       "*", vm, interval)
#     DatastoreIoWrite = (float(sum(statDatastoreIoWrite[0].value[0].value)) / statInt)
#     #Datastore Average Latency
#     statDatastoreLatRead = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'datastore.totalReadLatency.average')),
#                                       "*", vm, interval)
#     DatastoreLatRead = (float(sum(statDatastoreLatRead[0].value[0].value)) / statInt)
#     statDatastoreLatWrite = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'datastore.totalWriteLatency.average')),
#                                        "*", vm, interval)
#     DatastoreLatWrite = (float(sum(statDatastoreLatWrite[0].value[0].value)) / statInt)
 
#     #Network usage (Tx/Rx)
#     statNetworkTx = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'net.transmitted.average')), "", vm, interval)
#     networkTx = (float(sum(statNetworkTx[0].value[0].value) * 8 / 1024) / statInt)
#     statNetworkRx = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'net.received.average')), "", vm, interval)
#     networkRx = (float(sum(statNetworkRx[0].value[0].value) * 8 / 1024) / statInt)
 
#     print('networkRx:', networkRx)
#     print('networkTx:', networkTx)
#     print('\nNOTE: Any VM statistics are averages of the last {} minutes\n'.format(statInt / 3))
#     print('Server Name                    :', summary.config.name)
#     print('Description                    :', summary.config.annotation)
#     print('Guest                          :', summary.config.guestFullName)
#     if vm.rootSnapshot:
#         print('Snapshot Status                : Snapshots present')
#     else:
#         print('Snapshot Status                : No Snapshots')
#     print('VM .vmx Path                   :', summary.config.vmPathName)
#     try:
#         print('Virtual Disks                  :', disk_list[0])
#         if len(disk_list) > 1:
#             disk_list.pop(0)
#             for each_disk in disk_list:
#                 print('                                ', each_disk)
#     except IndexError:
#         pass
#     print('Virtual NIC(s)                 :', network_list[0])
#     if len(network_list) > 1:
#         network_list.pop(0)
#         for each_vnic in network_list:
#             print('                                ', each_vnic)
#     print('[VM] Limits                    : CPU: {}, Memory: {}'.format(vmcpulimit, vmmemlimit))
#     print('[VM] Reservations              : CPU: {}, Memory: {}'.format(vmcpures, vmmemres))
#     print('[VM] Number of vCPUs           :', summary.config.numCpu)
#     print('[VM] CPU Ready                 : Average {:.1f} %, Maximum {:.1f} %'.format((cpuReady / 20000 * 100),
#                                                                                        ((float(max(
#                                                                                            statCpuReady[0].value[
#                                                                                                0].value)) / 20000 * 100))))
#     print('[VM] CPU (%)                   : {:.0f} %'.format(cpuUsage))
#     print('[VM] Memory                    : {} MB ({:.1f} GB)'.format(summary.config.memorySizeMB, (float(summary.config.memorySizeMB) / 1024)))
#     print('[VM] Memory Shared             : {:.0f} %, {:.0f} MB'.format(
#         ((memoryShared / summary.config.memorySizeMB) * 100), memoryShared))
#     print('[VM] Memory Balloon            : {:.0f} %, {:.0f} MB'.format(
#         ((memoryBalloon / summary.config.memorySizeMB) * 100), memoryBalloon))
#     print('[VM] Memory Swapped            : {:.0f} %, {:.0f} MB'.format(
#         ((memorySwapped / summary.config.memorySizeMB) * 100), memorySwapped))
#     print('[VM] Memory Active             : {:.0f} %, {:.0f} MB'.format(
#         ((memoryActive / summary.config.memorySizeMB) * 100), memoryActive))
#     print('[VM] Datastore Average IO      : Read: {:.0f} IOPS, Write: {:.0f} IOPS'.format(DatastoreIoRead,
#                                                                                           DatastoreIoWrite))
#     print('[VM] Datastore Average Latency : Read: {:.0f} ms, Write: {:.0f} ms'.format(DatastoreLatRead,
#                                                                                       DatastoreLatWrite))
#     print('[VM] Overall Network Usage     : Transmitted {:.3f} Mbps, Received {:.3f} Mbps'.format(networkTx, networkRx))
#     print('[Host] Name                    : {}'.format(summary.runtime.host.name))
#     print('[Host] CPU Detail              : Processor Sockets: {}, Cores per Socket {}'.format(
#         summary.runtime.host.summary.hardware.numCpuPkgs,
#         (summary.runtime.host.summary.hardware.numCpuCores / summary.runtime.host.summary.hardware.numCpuPkgs)))
#     print('[Host] CPU Type                : {}'.format(summary.runtime.host.summary.hardware.cpuModel))
#     print('[Host] CPU Usage               : Used: {} Mhz, Total: {} Mhz'.format(
#         summary.runtime.host.summary.quickStats.overallCpuUsage,
#         (summary.runtime.host.summary.hardware.cpuMhz * summary.runtime.host.summary.hardware.numCpuCores)))
#     print('[Host] Memory Usage            : Used: {:.0f} GB, Total: {:.0f} GB\n'.format(
#         (float(summary.runtime.host.summary.quickStats.overallMemoryUsage) / 1024),
#         (float(summary.runtime.host.summary.hardware.memorySize) / 1024 / 1024 / 1024)))
 
 
# def StatCheck(perf_dict, counter_name):
#     counter_key = perf_dict[counter_name]
#     return counter_key
 
 
# def GetProperties(content, viewType, props, specType):
#     # Build a view and get basic properties for all Virtual Machines
#     objView = content.viewManager.CreateContainerView(content.rootFolder, viewType, True)
#     tSpec = vim.PropertyCollector.TraversalSpec(name='tSpecName', path='view', skip=False, type=vim.view.ContainerView)
#     pSpec = vim.PropertyCollector.PropertySpec(all=False, pathSet=props, type=specType)
#     oSpec = vim.PropertyCollector.ObjectSpec(obj=objView, selectSet=[tSpec], skip=False)
#     pfSpec = vim.PropertyCollector.FilterSpec(objectSet=[oSpec], propSet=[pSpec], reportMissingObjectsInResults=False)
#     retOptions = vim.PropertyCollector.RetrieveOptions()
#     totalProps = []
#     retProps = content.propertyCollector.RetrievePropertiesEx(specSet=[pfSpec], options=retOptions)
#     totalProps += retProps.objects
#     while retProps.token:
#         retProps = content.propertyCollector.ContinueRetrievePropertiesEx(token=retProps.token)
#         totalProps += retProps.objects
#     objView.Destroy()
#     # Turn the output in retProps into a usable dictionary of values
#     gpOutput = []
#     for eachProp in totalProps:
#         propDic = {}
#         for prop in eachProp.propSet:
#             propDic[prop.name] = prop.val
#         propDic['moref'] = eachProp.obj
#         gpOutput.append(propDic)
#     return gpOutput
def get_all_objs(content, vimtype):
    obj = []
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for managed_object_ref in container.view:
        # obj.update({managed_object_ref: managed_object_ref.name})
        obj.append(managed_object_ref)
    return obj



def main():    

          
        
          



    username = 'administrator@vsphere.local'
    # password = 'eRB$i5PUl@20211101'
    # vc_ip = '192.168.83.212'
    password = '123Qwe,.'
    vc_ip = '192.168.10.82'
    vc_port = '443'
 
    si = connect_vc(host=vc_ip, user=username, pwd=password, port=vc_port)
 
    content = si.RetrieveContent()

    getallvms=get_all_objs(content,[vim.VirtualMachine])

    # Provisioned disk space:Total allocated space that the virtual machine can commit up to. Includes vmdk, swap, snapshot, and other virtual machine files such as NVRAM, configuration files, and logs. This metric includes uncommitted space.
    for vm in getallvms:
            print(vm.config.name)
        # if vm.config.name=='Nginx':
            TotalUsedSpaceinGB=vm.summary.storage.committed/1024/1024/1024
            TotalProvisionedSpaceinGB=(vm.summary.storage.committed+vm.summary.storage.uncommitted)/1024/1024/1024
            # print(vm.summary.storage)
            # print('_________________________________')
            # vm_hardware = vm.config.hardware
            # disk_list = []
            # network_list = []
            # for each_vm_hardware in vm_hardware.device:
            #     if isinstance(each_vm_hardware,vim.vm.device.VirtualDisk): 
            #         # print(each_vm_hardware)
            #         if (each_vm_hardware.key >= 2000) and (each_vm_hardware.key < 3000):
            #             disk_list.append('{} | {:.1f}GB | Thin: {} | {}'.format(each_vm_hardware.deviceInfo.label,
            #                                                         each_vm_hardware.capacityInKB/1024/1024,
            #                                                         each_vm_hardware.backing.thinProvisioned,
            #                                                         each_vm_hardware.backing.fileName))
            #     # elif (each_vm_hardware.key >= 4000) and (each_vm_hardware.key < 5000):
            #     #     network_list.append('{} | {} | {}'.format(each_vm_hardware.deviceInfo.label,
            #     #                                                 each_vm_hardware.deviceInfo.summary,
            #     #                                                 each_vm_hardware.macAddress))



            # print(disk_list)
            # print(network_list)
            des_disks=[]
            ext_disks=[]
            disks=[]
            for file in vm.layoutEx.file:
                    # print(file)
                    
                    #在不同的类型的datastore，diskDescriptor类型的文件有不同的表现，vsan中的diskDescriptor类型的文件就代表硬盘，该文件的大小也就是硬盘的大小，VMFS下diskDescriptor文件只是一个描述文件，体积很小，代表磁盘的是diskExtent文件
                    #所以在vmfs情况下，需要将diskExtent和diskDescriptor2个文件进行合并
                    des_disk={}
                    ext_disk={}
                    if file.type=="diskDescriptor":
                        
                        #从路径获取磁盘文件名
                        shortname=file.name.split("/")[-1]
                        # print("file name:"+shortname)
                        # print("file size:"+str(file.size))
                        rx=re.search('(.*)-(000\d\d\d\.vmdk)', shortname)
                        if  rx is None:
                            # disk['backingObjectId']=file.backingObjectId
                            des_disk['disk_name']=shortname
                            des_disk['disk_path']=file.name
                            des_disk['used_disk_size']=file.size
                            des_disk['disk_snap_num']=0
                            des_disk['disk_snap_size']=0
                            des_disks.append(des_disk)

                        else:
                            for i in range(len(des_disks)):
                                if des_disks[i]['disk_name']==rx.group(1)+".vmdk":
                                    des_disks[i]['used_disk_size']+=file.size
                                    des_disks[i]['disk_snap_num']+=1
                                    des_disks[i]['disk_snap_size']+=file.size
                    if file.type=='diskExtent':
                        shortname=file.name.split("/")[-1]
                        rx=re.search('(.*)-(000\d\d\d\-delta.vmdk)', shortname)
                        if  rx is None:
                            # disk['backingObjectId']=file.backingObjectId
                            ext_disk['disk_name']=shortname
                            ext_disk['disk_path']=file.name
                            ext_disk['used_disk_size']=file.size
                            ext_disk['disk_snap_num']=0
                            ext_disk['disk_snap_size']=0
                            ext_disks.append(ext_disk)

                        else:
                            for i in range(len(ext_disks)):
                                if ext_disks[i]['disk_name']==rx.group(1)+"-flat.vmdk":
                                    ext_disks[i]['used_disk_size']+=file.size
                                    ext_disks[i]['disk_snap_num']+=1
                                    ext_disks[i]['disk_snap_size']+=file.size
                        
                    #将diskExtent和diskDescriptor2个文件进行合并
                    # des_disks:[{'disk_name': 'Niginx.vmdk', 'disk_path': '[SC01] Niginx/Niginx.vmdk', 'used_disk_size': 967, 'disk_snap_num': 1, 'disk_snap_size': 359}]
                    # ext_disks:[{'disk_name': 'Niginx-flat.vmdk', 'disk_path': '[SC01] Niginx/Niginx-flat.vmdk', 'used_disk_size': 11501130752, 'disk_snap_num': 1, 'disk_snap_size': 524288}]
                    
            if len(ext_disks)>0:
                for ext_disk in ext_disks:
                    ext_disk_short_name=ext_disk['disk_name'].split('-flat.vmdk')[0]
                    for des_disk in des_disks:
                        if des_disk['disk_name'].split('.vmdk')[0]==ext_disk_short_name:
                            consolidated_disk={}
                            consolidated_disk['disk_name']=des_disk['disk_name']
                            consolidated_disk['used_disk_size']=des_disk['used_disk_size']+ext_disk['used_disk_size']
                            consolidated_disk['disk_snap_size']=des_disk['disk_snap_size']+ext_disk['disk_snap_size']
                            consolidated_disk['disk_snap_num']=des_disk['disk_snap_num']
                            consolidated_disk['disk_path']=des_disk['disk_path']
                            disks.append(consolidated_disk)
                        else:
                            consolidated_disk={}
                            consolidated_disk['disk_name']=des_disk['disk_name']
                            consolidated_disk['used_disk_size']=des_disk['used_disk_size']
                            consolidated_disk['disk_snap_size']=des_disk['disk_snap_size']
                            consolidated_disk['disk_snap_num']=des_disk['disk_snap_num']
                            consolidated_disk['disk_path']=des_disk['disk_path']
                            disks.append(consolidated_disk)

            else:
                disks=des_disks
            
            print('DES DISK:{}'.format(des_disks))
            print('EXT DISK:{}'.format(ext_disks))
            print('DISK:{}'.format(disks))

                    




            i=0
            for dev in vm.config.hardware.device:
                if isinstance(dev,vim.vm.device.VirtualDisk):
                    disks[i]['provisioned_disk_size']=dev.capacityInBytes
                    print(i)
                    i=i+1


            

# #     # Get vCenter date and time for use as baseline when querying for counters
# #     vchtime = si.CurrentTime()
 
# #     # Get all the performance counters
# #     perf_dict = {}
# #     perfList = content.perfManager.perfCounter
# #     for counter in perfList:
# #         counter_full = "{}.{}.{}".format(counter.groupInfo.key, counter.nameInfo.key, counter.rollupType)
# #         perf_dict[counter_full] = counter.key
 
# #     retProps = GetProperties(content, [vim.VirtualMachine], ['name', 'runtime.powerState'], vim.VirtualMachine)
 
# #     #Find VM supplied as arg and use Managed Object Reference (moref) for the PrintVmInfo
# #     for vm in retProps:
# #         PrintVmInfo(vm['moref'], content, vchtime, 20, perf_dict)
# #         break
 
 
# Start program
if __name__ == "__main__":
    main()
