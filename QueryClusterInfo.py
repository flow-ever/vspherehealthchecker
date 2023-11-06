from decimal import Decimal
import datetime
import json
import os
from pyVmomi import vim
import vsanmgmtObjects
import vsanapiutils
from packaging.version import Version
import logging
from pyVim.connect import SmartConnect, Disconnect
import atexit
import ssl
import sys

# # Check if the command-line arguments are provided
# if len(sys.argv) != 4:
#     print("Usage: "+ __name__+" <vchost> <vcuser> <vcpassword>")
#     sys.exit(1)

# # Retrieve the arguments
# vchost = sys.argv[1]
# vcuser = sys.argv[2]
# vcpassword = sys.argv[3]

# s = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
# s.verify_mode = ssl.CERT_NONE

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
        elif isinstance(obj, bool):
           return str(obj).lower()
        else:
            return super(MyEncoder, self).default(obj)

def str2list(string):
    li=list(string.split(","))
    return li

def get_all_objs(content, vimtype):
    obj = []
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for managed_object_ref in container.view:
        # obj.update({managed_object_ref: managed_object_ref.name})
        obj.append(managed_object_ref)
    return obj



def QueryClustersInfo(si,vchost):
    logger.info("开始收集集群信息")
    content=si.content
    getCluster=get_all_objs(content,[vim.ClusterComputeResource])
    clusters=[]
    vsan_info=[]
    for cls in getCluster: 
        logger.info("开始收集集群："+ cls.name +" 信息")  
        cluster_config={}
    
        cls_hosts=[]
        for host in cls.host:
            cls_hosts.append(host.name)


    #retrive ha configuration 
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

        feature_capabilities = evc_state.featureCapability

        for capability in feature_capabilities:
                print("Feature Capability\n") 
                print(capability.featureName) 
                print(capability.key) 
                print(capability.value) 
                print("-------------") 

        features_masked = evc_state.featureMask

        for mask in features_masked:
                print("Feature Masked\n") 
                print(mask.featureName) 
                print(mask.key) 
                print(mask.value) 
                print("-------------" )   

        cluster_config['name']=cls.name
        cluster_config['parent']=cls.parent
        cluster_config['hosts']=cls_hosts
        cluster_config['ha_config']=ha_config
        cluster_config['drs_config']=drs_config
        cluster_config['evc_config']=evc_config
    #    print(cluster_config['ha_config'])
        clusters.append(cluster_config)

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
            vsan_info.append({"health_test":test_list})
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
            vsan_info.append(dataEfficientState_dict)

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
            vsan_info.append({"cluster_disMapInfo":cluster_diskMapInfo})
            
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
            vsan_info.append({"cluster_diskSmartStat":cluster_smartstat})


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

            vsan_info.append({"vsan_perf":vsan_perf})
            cluster_config['vsan_enabled']=True
            cluster_config['vsan_info']=vsan_info

            clusters.append(cluster_config)


    
    print("write retrieved information abouts vsphere cluster(s) in to json file {}".format(cluster_json_file))
    with open(cluster_json_file,'w') as f:
        json.dump(clusters,f,indent=4,ensure_ascii=False,default=str,cls=MyEncoder)
        logger.info("集群信息写入文件："+ cluster_json_file)   
    f.close
    print("All cluster(s) information are saved!")
    logger.info("the information acquisition of cluster(s) is finished!") 


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
    cluster_json_file=os.path.join(cwd,'data',"cluster-"+current_time+".json")

    logfile_path=os.path.join(cwd,'data','log',"clusterInfo_gathering.log")
    log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
    logger=logging.getLogger('cluster_logger')
    fh=logging.FileHandler(filename=logfile_path,mode='a')
    fh.setLevel(logging.INFO)
    fh.setFormatter(log_formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)

    s = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    s.verify_mode = ssl.CERT_NONE
    si=establish_connection(vchost,vcuser,vcpassword)
    QueryClustersInfo(si,vchost)