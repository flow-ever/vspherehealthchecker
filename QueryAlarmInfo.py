from datetime import datetime
import os
import atexit
from pyVmomi import vim
import re
import json
import ssl
import sys
from pyVim.connect import SmartConnect,Disconnect,SmartConnectNoSSL

import logging



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


def establish_connection(vchost,vcuser,vcpassword):
    try:
        si = SmartConnectNoSSL(host=vchost, user=vcuser, pwd=vcpassword)
        atexit.register(Disconnect, si)
        return si
    except Exception as e:
        print(f"Failed to connect to vCenter at {vchost}: {e}")
        logger.error(f"Failed to connect to vCenter at {vchost}: {e}")
        return None





def QueryAlarmInfo(vchost,vcuser,vcpassword):

    cwd = os.getcwd()
    current_time=datetime.now().strftime('%Y%m%d%H%M%S')    
    alarm_json_file=os.path.join(cwd,'data',"alarm-"+current_time+".json")
    logfile_path=os.path.join(cwd,'data','log',"alarmInfo_gathering.log")
    log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
    logger=logging.getLogger('alarm_logger')
    fh=logging.FileHandler(filename=logfile_path,mode='a')
    fh.setLevel(logging.INFO)
    fh.setFormatter(log_formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)

    logger.info("开始收集Alarm信息!")

    si=establish_connection(vchost,vcuser,vcpassword)
    content = si.content
    allAlarms=content.rootFolder.triggeredAlarmState
    alarm_list=[]
    for alarm in allAlarms:
            alarm_dict={}
        # if not alarm.acknowledged:
            if alarm.overallStatus=='yellow' or alarm.overallStatus=='red':
                # print("--"*30)
                # print(type(alarm.entity))
                rx=re.search("\'(?P<classname>.*)\'",str(type(alarm.entity)))
                entity_type=rx.group('classname')
                
                # print("{} {} {}  {}  {}  {} {}" .format(alarm.entity.name,entity_type.split(".")[-1],alarm.alarm.info.name,alarm.alarm.info.description,alarm.overallStatus,\
                #                             alarm.time,alarm.acknowledged))
                alarm_dict['entity_name']=alarm.entity.name
                alarm_dict['time']=alarm.time
                alarm_dict['entity_type']=entity_type.split(".")[-1]
                alarm_dict['alarm_name']=alarm.alarm.info.name
                alarm_dict['alarm_decription']=alarm.alarm.info.description
                alarm_dict['alarm_status']=alarm.overallStatus
                alarm_dict['acknowledged']=alarm.acknowledged
                alarm_list.append(alarm_dict)


            

    print("write retrieved information abouts alarms of vsphere  in to json file {}".format(alarm_json_file))
    with open(alarm_json_file,'a') as f:
        json.dump(alarm_list,f,indent=4,ensure_ascii=False,default=str,cls=MyEncoder)
        logger.info("Alarm信息写入文件："+alarm_json_file)
    f.close
    print("All Alarm(s) information are saved!")
    logger.info("the information acquisition of alarm(s) is finished!")    

if __name__=="__main__":
    # Check if the command-line arguments are provided
    if len(sys.argv) != 4:
        print("Usage: "+ os.path.basename(__file__)+" <vchost> <vcuser> <vcpassword>")
        sys.exit(1)

    # Retrieve the arguments
    vchost = sys.argv[1]
    vcuser = sys.argv[2]
    vcpassword = sys.argv[3]
    


    si=establish_connection(vchost,vcuser,vcpassword)
    QueryAlarmInfo(si)

# time_filter = vim.event.EventFilterSpec.ByTime()
# now = datetime.now()
# time_filter.beginTime = now - timedelta(hours=1)
# time_filter.endTime = now
# event_type_list = []
# # If you want to also filter on certain events, uncomment the below event_type_list.
# # The EventFilterSpec full params details:
# # https://pubs.vmware.com/vsphere-6-5/topic/com.vmware.wssdk.smssdk.doc/vim.event.EventFilterSpec.html
# # event_type_list = ['VmRelocatedEvent', 'DrsVmMigratedEvent', 'VmMigratedEvent']
# category=["info"] #EventSeverity: error,info,user,warning
# filter_spec = vim.event.EventFilterSpec(eventTypeId=event_type_list, time=time_filter)


# eventManager = si.content.eventManager
# event_collector = eventManager.CreateCollectorForEvents(filter_spec)
# page_size = 1000 # The default and also the max event number per page till vSphere v6.5, you can change it to a smaller value by SetCollectorPageSize().
# events = []

# while True:
#   # If there's a huge number of events in the expected time range, this while loop will take a while.
#   events_in_page = event_collector.ReadNextEvents(page_size)
#   num_event_in_page = len(events_in_page)
#   if num_event_in_page == 0:
#     break
#   events.extend(events_in_page) # or do other things on the collected events
# # Please note that the events collected are not ordered by the event creation time, you might find the first event in the third page for example.

# print(
#     "Got totally {} events in the given time range from {} to {}.".format(
#         len(events), time_filter.beginTime, time_filter.endTime
#     )
# )


