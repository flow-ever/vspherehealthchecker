import requests
import os
import datetime
import sys
import logging



def QueryiDRAC(host,ipmiuser,ipmipass,fname):
    logger.info('登录主机：'+host+" 获取IPMI日志信息。")

    # host=['192.168.10.230','192.168.10.231','192.168.10.232','192.168.10.237']
    system = requests.get('https://'+host+'/redfish/v1/Systems/System.Embedded.1',verify=False,auth=(ipmiuser,ipmipass))
    storage = requests.get('https://'+host+'/redfish/v1/Systems/System.Embedded.1/Storage/Controllers/RAID.Integrated.1-1',verify=False,auth=(ipmiuser,ipmipass))
    systemData = system.json()
    storageData = storage.json()
    file=open(fname,'a')
    file.writelines("Model: {} \n".format(systemData[u'Model']),\
                     "Manufacturer: {} \n".format(systemData[u'Manufacturer']),\
                     "Service tag {}\n".format(systemData[u'SKU']),\
                     "Serial number: {}\n".format(systemData[u'SerialNumber']),\
                     "Hostname: {}\n".format(systemData[u'HostName']),\
                     "Power state: {}\n".format(systemData[u'PowerState']),\
                     "Asset tag: {}\n".format(systemData[u'AssetTag']),\
                     "Memory size: {}\n".format(systemData[u'MemorySummary']    [u'TotalSystemMemoryGiB']),\
                     "CPU type: {}\n".format(systemData[u'ProcessorSummary'][u'Model']),\
                     "System status: {}\n".format(systemData[u'Status'][u'Health']),\
                     
                     )
    print("Model: {}".format(systemData[u'Model']))
    print ("Manufacturer: {}".format(systemData[u'Manufacturer']))
    print ("Service tag {}".format(systemData[u'SKU']))
    print ("Serial number: {}".format(systemData[u'SerialNumber']))
    print ("Hostname: {}".format(systemData[u'HostName']))
    print ("Power state: {}".format(systemData[u'PowerState']))
    print ("Asset tag: {}".format(systemData[u'AssetTag']))
    print ("Memory size: {}".format(systemData[u'MemorySummary']    [u'TotalSystemMemoryGiB']))
    print ("CPU type: {}".format(systemData[u'ProcessorSummary'][u'Model']))
    print ("Number of CPUs: {}".format(systemData[u'ProcessorSummary'][u'Count']))
    print ("System status: {}".format(systemData[u'Status'][u'Health']))
    # print ("RAID health: {}".format(storageData[u'Status'][u'Health']))

    sel_log = requests.get('https://'+host+'/redfish/v1/Managers/iDRAC.Embedded.1/Logs/Sel',verify=False,auth=(ipmiuser,ipmipass))
    systemData = sel_log.json()
    for logEntry in systemData[u'Members']:
        print(logEntry)
        file.write("{}\n".format(logEntry))
    file.close()


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


    logfile_path=os.path.join(cwd,"IPMIInfo_gathering.log")
    log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
    logger=logging.getLogger('ipmi_logger')
    fh=logging.FileHandler(filename=logfile_path,mode='a')
    fh.setLevel(logging.INFO)
    fh.setFormatter(log_formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)

    
    QueryiDRAC(host=ipmi_host,ipmiuser=ipmi_user,ipmipass=ipmi_password,fname=ipmi_file)


