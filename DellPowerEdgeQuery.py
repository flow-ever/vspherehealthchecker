import requests
import os
import sys
import logging
import json



def QueryiDRAC(host,ipmiuser,ipmipass,fname):
    logger.info('登录主机：'+host+" 获取IPMI日志信息。")
    ipmi_info=[]
    ipmi={}
    # host=['192.168.10.230','192.168.10.231','192.168.10.232','192.168.10.237']
    try:
        system = requests.get('https://'+host+'/redfish/v1/Systems/System.Embedded.1',verify=False,auth=(ipmiuser,ipmipass))
        if system.status_code==401:
            logger.error('connect to '+ host +' failed! status code:'+str(system.status_code)+',authentication failed!')
        elif  system.status_code==200:
            logger.error('Successfully connected to '+ host +'!')
            systemData = system.json()
        elif not system.ok:
            logger.error('connect to '+ host +' failed! status code:'+str(system.status_code)+',!')
    except requests.exceptions.RequestException as e:
        logger.error(e)    
    
    try:
        storage = requests.get('https://'+host+'/redfish/v1/Systems/System.Embedded.1/Storage/Controllers/RAID.Integrated.1-1',verify=False,auth=(ipmiuser,ipmipass))
        if system.status_code==401:
            logger.error('connect to '+ host +' failed! status code:'+str(system.status_code)+',authentication failed!')
        elif  system.status_code==200:
            logger.error('Successfully connected to '+ host +'!')
            storageData = storage.json()
        elif not system.ok:
            logger.error('connect to '+ host +' failed! status code:'+str(system.status_code)+',!')
    except requests.exceptions.RequestException as e:
        logger.error(e)    
    

    

                     
    logger.info("Model: {}".format(systemData[u'Model']))
    logger.info ("Manufacturer: {}".format(systemData[u'Manufacturer']))
    logger.info("Service tag {}".format(systemData[u'SKU']))
    logger.info("Serial number: {}".format(systemData[u'SerialNumber']))
    logger.info("Hostname: {}".format(systemData[u'HostName']))
    logger.info("Power state: {}".format(systemData[u'PowerState']))
    logger.info("Asset tag: {}".format(systemData[u'AssetTag']))
    logger.info("Memory size: {}".format(systemData[u'MemorySummary']    [u'TotalSystemMemoryGiB']))
    logger.info("CPU type: {}".format(systemData[u'ProcessorSummary'][u'Model']))
    logger.info("Number of CPUs: {}".format(systemData[u'ProcessorSummary'][u'Count']))
    logger.info("System status: {}".format(systemData[u'Status'][u'Health']))
    # print ("RAID health: {}".format(storageData[u'Status'][u'Health']))

    
    
    try:
        sel_log = requests.get('https://'+host+'/redfish/v1/Managers/iDRAC.Embedded.1/Logs/Sel',verify=False,auth=(ipmiuser,ipmipass))
        if system.status_code==401:
            logger.error('connect to '+ host +' failed! status code:'+str(system.status_code)+',authentication failed!')
        elif  system.status_code==200:
            logger.error('Successfully connected to '+ host +'!')
            LogData = sel_log.json()
        elif not system.ok:
            logger.error('connect to '+ host +' failed! status code:'+str(system.status_code)+',!')
    except requests.exceptions.RequestException as e:
        logger.error(e) 


    ipmi['host']=host
    ipmi['systemData']=systemData
    ipmi['StorageData']=storageData
    ipmi['LogData']=LogData
    
    #如果文件存在，从文件中读入数据
    if os.path.exists(fname):
        try:
            with open(fname,'r') as f:
                ipmi_info=json.load(f)
            f.close()
        except json.decoder.JSONDecodeError: #file is empty
            logger.critical(fname+':this json file is empty ')
    else:
        #文件不存在，创建文件
        with open(fname,'x') as f:
            logger.info('create file:'+fname)
            
        f.close()

    ipmi_info.append(ipmi)


    with open(fname,'w') as f:
        json.dump(ipmi_info,f,indent=4,ensure_ascii=False,default=str)    
        logger.info('write data to json file')
    f.close()


if __name__=="__main__":
    # Check if the command-line arguments are provided
    if len(sys.argv) != 5:
        print("Usage: "+ os.path.basename(__file__)+" <ipmi_host> <ipmi_user> <ipmi_password> <ipmi_file>")
        sys.exit(1)

    # Retrieve the arguments
    ipmi_host = sys.argv[1]
    ipmi_user = sys.argv[2]
    ipmi_password = sys.argv[3]
    ipmi_file = sys.argv[4]

    cwd = os.getcwd()


    logfile_path=os.path.join(cwd,'data','log',"IPMIInfo_gathering.log")
    log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
    logger=logging.getLogger('ipmi_logger')
    fh=logging.FileHandler(filename=logfile_path,mode='a')
    fh.setLevel(logging.INFO)
    fh.setFormatter(log_formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)

    
    QueryiDRAC(host=ipmi_host,ipmiuser=ipmi_user,ipmipass=ipmi_password,fname=ipmi_file)


