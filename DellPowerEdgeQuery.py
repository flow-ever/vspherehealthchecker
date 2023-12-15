import requests
import os
import sys
import logging
import json
from datetime import datetime
import re

cwd=os.getcwd()
data_dir=os.path.join(cwd,'data')
current_time=datetime.now().strftime('%Y%m%d%H%M%S')
logfile_path=os.path.join(data_dir,'log',"IPMIInfo_gathering.log")
log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
logger=logging.getLogger('ipmi_logger')
fh=logging.FileHandler(filename=logfile_path,mode='a')
fh.setLevel(logging.INFO)
fh.setFormatter(log_formatter)
logger.addHandler(fh)
logger.setLevel(logging.INFO)

def api_call(url,user,password):
    try:
        response = requests.get(url,verify=False,auth=(user,password),timeout=12)
        if response.status_code==401:
            logger.error('connect to '+ url +' failed! status code:'+str(response.status_code)+',authentication failed!')
            sys.exit(0)
        elif  response.status_code==200:
            logger.info('Successfully connected to '+ url +'!')
            if response.json() is not None:
                response_Data = response.json()
            else:
                logger.error('response.json() is None')
                response_Data={}
        elif not response.ok:
            logger.error('connect to '+ url +' failed! status code:'+str(response.status_code)+'!')
            response_Data={}
    except requests.exceptions.RequestException as e:
        logger.error("Access "+url+" Error:")
        logger.error(e)  
        response_Data={}
    finally:
        return response_Data

    



def QueryiDRAC(host,ipmiuser,ipmipass):


    logger.info('登录主机：'+host+" 获取IPMI日志信息。")
    print('登录主机：'+host+" 获取IPMI日志信息。")
    ipmi_info=[]
    ipmi={}
    
    
    url='https://'+host+'/redfish/v1/Systems/System.Embedded.1'
    systemData={}
    
    response=api_call(url,ipmiuser,ipmipass)
    systemData[u'BiosVersion']=response.get(u'BiosVersion')
    systemData[u'Model']=response.get(u'Model')
    systemData[u'Manufacturer']=response.get(u'Manufacturer')

    fanData={}
    fans=response.get(u'Links')['CooledBy']
    keys=[ u'LowerThresholdCritical', u'LowerThresholdFatal', u'LowerThresholdNonCritical', u'MaxReadingRange', u'MinReadingRange', u'Status', u'UpperThresholdCritical', u'UpperThresholdFatal', u'UpperThresholdNonCritical',u'Reading']
    for fan in fans:
        fan_url='https://'+host+fan[u'@odata.id']
        fan_reponse=api_call(fan_url,ipmi_user,ipmi_password)
        fanData[fan_reponse[u'FanName']]={_k:fan_reponse[_k] for _k in keys}
    systemData[u'fanCount']=response.get(u'Links')['CooledBy@odata.count']
    systemData[u'fans']=fanData

    psData={}
    pss=response.get(u'Links')['PoweredBy']
    keys=[]
    for ps in pss:
        ps_url='https://'+host+ps[u'@odata.id']
        ps_response=api_call(ps_url,ipmi_user,ipmi_password)
        psData[u'Name']={'Health':ps_response[u'Status'][u'Health'],
                          'present':ps_response[u'Status'][u'State'],
                          'PowerInputWatts':ps_response[u'PowerInputWatts'],
                          'OutputWattage':ps_response[u'InputRanges'][0][u'OutputWattage'],
                          'InputType':ps_response[u'InputRanges'][0][u'InputType'],
                          'Model':ps_response[u'Model'],
                          'SparePartNumber':ps_response[u'SparePartNumber'],
                          'SerialNumber':ps_response[u'SerialNumber'],
                          }
    systemData[u'psCount']=response.get(u'Links')['PoweredBy@odata.count'] 
    systemData[u'ps']=psData  

    systemData[u'MemorySummary']=response.get(u'MemorySummary')

    memData={}
    mem_url='https://'+host+response.get(u'Memory')['@odata.id']
    mem_reponse=api_call(mem_url,ipmi_user,ipmi_password)
    keys=[u'CapacityMiB', u'DataWidthBits', u'ErrorCorrection', u'Manufacturer', u'MemoryDeviceType', u'OperatingSpeedMhz', u'PartNumber', u'RankCount', u'SerialNumber']
    for i in mem_reponse[u'Members']:
        dimm = i['@odata.id'].split("/")[-1]
        try:
            dimm_slot = re.search("DIMM.+",dimm).group()
        except:
            logging.error("\n- FAIL, unable to get dimm slot info")
            sys.exit(0)
        
        dimm_url='https://'+host+i['@odata.id']
        dimm_reponse=api_call(dimm_url,ipmi_user,ipmi_password)
        memData[dimm_reponse['Name']]={_k:dimm_reponse[_k] for _k in keys}
        memData[dimm_reponse['Name']]['Status']=dimm_reponse['Status']['Health']

    systemData[u'DIMM']=memData


    interfaceData={}
    ints_url='https://'+host+response.get(u'NetworkInterfaces')['@odata.id']
    ints_reponse=api_call(ints_url,ipmi_user,ipmi_password)
    for int in ints_reponse[u'Members']:
        int_url='https://'+host+int[u'@odata.id']
        int_reponse=api_call(int_url,ipmi_user,ipmi_password)
        portsData={}
        ports_url='https://'+host+int_reponse['NetworkPorts']['@odata.id']
        ports_reponse=api_call(ports_url,ipmi_user,ipmi_password)
        for port in ports_reponse[u'Members']:
            port_url='https://'+host+port[u'@odata.id']
            port_reponse=api_call(port_url,ipmi_user,ipmi_password)
            portsData[port_reponse['Id']]={'ActiveLinkTechnology':port_reponse['ActiveLinkTechnology'],
                                           'LinkStatus':port_reponse['LinkStatus'],
                                           'PhysicalPortNumber':port_reponse['PhysicalPortNumber'],
                                           'Status':port_reponse['Status'],
                                           'SupportedLinkCapabilities':port_reponse['SupportedLinkCapabilities'],
                                           
                                           }
        interfaceData[int['NetworkPorts']]=portsData
    
    systemData[u'interface']=interfaceData



    systemData[u'ProcessorSummary']=response.get(u'ProcessorSummary')
    processorData={}
    processors_url='https://'+host+response.get(u'Processors')['@odata.id']
    processors_reponse=api_call(processors_url,ipmi_user,ipmi_password)
    processorData['ProcessorsCount']=processors_reponse[u'Members@odata.count']
    for processor in   processors_reponse[u'Members']:
        processor_url='https://'+host+processor[u'@odata.id']
        processor_response=api_call(processor_url,ipmi_user,ipmi_password)
        print(processor_response)





    systemData[u'SerialNumber']=response.get(u'SerialNumber')
    systemData[u'Status']=response.get(u'Status')['HealthRollup']
    systemData[u'ServiceTag']=response.get(u'SKU')

    # try:
    #     url='https://'+host+'/redfish/v1/Systems/System.Embedded.1'
    #     system = requests.get(url,verify=False,auth=(ipmiuser,ipmipass),timeout=12)
    #     if system.status_code==401:
    #         logger.error('connect to '+ host +' failed! status code:'+str(system.status_code)+',authentication failed!')
    #     elif  system.status_code==200:
    #         logger.info('Successfully connected to '+ host +'!')
    #         if system.json() is not None:

    #             systemData = system.json()

    #         else:
    #             print('system.json() is None')
    #             systemData={}
    #     elif not system.ok:
    #         logger.error('connect to '+ url +' failed! status code:'+str(system.status_code)+'!')
    #         systemData={}
    # except requests.exceptions.RequestException as e:
    #     logger.error("Access "+url+" Error:")
    #     logger.error(e)  
    #     systemData={}

    url='https://'+host+'/redfish/v1/Systems/System.Embedded.1/Storage'
    storageData=api_call(url,ipmiuser,ipmipass)
    
    drive_list=[]
    controller_list=storageData.get(u'Members')
    # print(controller_list)
    for ctrl in controller_list:
        sub_url='https://'+host+ctrl[u'@odata.id']
        # print(sub_url)
        response=api_call(sub_url,ipmi_user,ipmi_password)
        controller=response[u'Name']
        if response.get(u'Drives'):
            for drv in response.get(u'Drives'):
                drive_list.append((controller,drv))
    #get drives
    drive_data={}
    keys = [u'SerialNumber', u'PartNumber', u'Manufacturer', u'MediaType', u'Model', u'FailurePredicted', u'CapacityBytes', u'RotationSpeedRPM', u'Status', u'PredictedMediaLifeLeftPercent', u'Revision']
    for controller,drv in drive_list:
        sub_url='https://'+host+drv[u'@odata.id']
        metadata=api_call(sub_url,ipmi_user,ipmi_password)
        drive_data[metadata[u'Name']] = {_k:metadata[_k] for _k in keys}
        drive_data[metadata[u'Name']][u'Controller'] = controller



    
    
    # try:
    #     # url='https://'+host+'/redfish/v1/Systems/System.Embedded.1/Storage/Controllers/RAID.Integrated.1-1'
    #     url='https://'+host+'/redfish/v1/Systems/System.Embedded.1/Storage'
    #     storage = requests.get(url,verify=False,auth=(ipmiuser,ipmipass),timeout=12)
    #     if storage.status_code==401:
    #         logger.error('connect to '+ host +' failed! status code:'+str(storage.status_code)+',authentication failed!')
    #     elif  storage.status_code==200:
    #         logger.info('Successfully connected to '+ url +'!')
    #         drive_list=[]
    #         controller_list=storage.get(u'Members')
    #         num_controllers=len(controller_list)
    #         for cntrl in controller_list:

    #         storageData = storage.json()            
    #     elif not storage.ok:
    #         logger.error('connect to '+ url +' failed! status code:'+str(storage.status_code)+'!')
    #         storageData={}
    # except requests.exceptions.RequestException as e:
    #     logger.error("Access "+url+" Error:")
    #     logger.error(e)
    #     storageData={}

    keys = [u'Created', u'Message', u'SensorType', u'Severity', u'EntryType']
    url='https://'+host+'/redfish/v1/Managers/iDRAC.Embedded.1/Logs/Sel'
    response=api_call(url,ipmiuser,ipmipass)
    logData={}
    log_entries=response.get(u'Members')
    for log in log_entries:
        logData[log[u'Id']]={_k:log[_k] for _k in keys}




                     
    # logger.info("Model: {}".format(systemData[u'Model']))
    # logger.info ("Manufacturer: {}".format(systemData[u'Manufacturer']))
    # logger.info("Service tag {}".format(systemData[u'SKU']))
    # logger.info("Serial number: {}".format(systemData[u'SerialNumber']))
    # logger.info("Hostname: {}".format(systemData[u'HostName']))
    # logger.info("Power state: {}".format(systemData[u'PowerState']))
    # logger.info("Asset tag: {}".format(systemData[u'AssetTag']))
    # logger.info("Memory size: {}".format(systemData[u'MemorySummary']    [u'TotalSystemMemoryGiB']))
    # logger.info("CPU type: {}".format(systemData[u'ProcessorSummary'][u'Model']))
    # logger.info("Number of CPUs: {}".format(systemData[u'ProcessorSummary'][u'Count']))
    # logger.info("System status: {}".format(systemData[u'Status'][u'Health']))
    # print ("RAID health: {}".format(storageData[u'Status'][u'Health']))

    
    
    # try:
    #     url='https://'+host+'/redfish/v1/Managers/iDRAC.Embedded.1/Logs/Sel'
    #     sel_log = requests.get(url,verify=False,auth=(ipmiuser,ipmipass),timeout=12)
    #     if sel_log.status_code==401:
    #         logger.error('connect to '+ host +' failed! status code:'+str(sel_log.status_code)+',authentication failed!')
    #     elif  sel_log.status_code==200:
    #         logger.info('Successfully connected to '+ url +'!')
    #         LogData = sel_log.json()
    #     elif not sel_log.ok:
    #         logger.error('connect to '+ url +' failed! status code:'+str(sel_log.status_code)+'!')
    #         LogData={}
    # except requests.exceptions.RequestException as e:
    #     logger.error("Access "+url+" Error:")
    #     logger.error(e) 
    #     LogData={}


    ipmi['host']=host
    ipmi['systemData']=systemData
    ipmi['storageData']=drive_data
    ipmi['LogData']=logData
    
    
    # #如果文件存在，从文件中读入数据
    # if os.path.exists(fname):
    #     try:
    #         with open(fname,'r') as f:
    #             ipmi_info=json.load(f)
    #         f.close()
    #     except json.decoder.JSONDecodeError: #file is empty
    #         logger.critical(fname+':this json file is empty ')
    # else:
    #     #文件不存在，创建文件
    #     with open(fname,'x') as f:
    #         logger.info('create file:'+fname)
            
    #     f.close()

    ipmi_info.append(ipmi)

    #获取Dell服务器的IPMI日志

    ipmi_file=os.path.join(data_dir,"ipmi-"+host+'-'+current_time+".json")
    
    if (os.path.exists(ipmi_file) == False):
      f = open(ipmi_file, "w")
      logger.info("create file:"+ipmi_file)

    with open(ipmi_file,'w') as f:
        json.dump(ipmi_info,f,indent=4,ensure_ascii=False,default=str)    
        logger.info('write data to json file:'+ipmi_file)
        logger.info('the information acquisition of ipmi host(s) is finished!')
    f.close()


if __name__=="__main__":
    # Check if the command-line arguments are provided
    if len(sys.argv) != 4:
        print("Usage: "+ os.path.basename(__file__)+" <ipmi_host> <ipmi_user> <ipmi_password> <ipmi_file>")
        sys.exit(1)

    # Retrieve the arguments
    ipmi_host = sys.argv[1]
    ipmi_user = sys.argv[2]
    ipmi_password = sys.argv[3]
    # ipmi_file = sys.argv[4]

    
    QueryiDRAC(host=ipmi_host,ipmiuser=ipmi_user,ipmipass=ipmi_password)


