import time,datetime
import os,shutil
import subprocess
import multiprocessing 
import sys
import re
import json
from decimal import Decimal
from collections import defaultdict
import logging




from flask import Flask,render_template,request,Response,redirect,url_for


mainlogfile_path=os.path.join(os.getcwd(),"main.log")
log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
logger=logging.getLogger('main_logger')
fh=logging.FileHandler(filename=mainlogfile_path,mode='a')
fh.setLevel(logging.INFO)
fh.setFormatter(log_formatter)
logger.addHandler(fh)
logger.setLevel(logging.INFO)


app=Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
app.jinja_env.add_extension('jinja2.ext.loopcontrols')
python_path=sys.executable



logger.info(app.name+" 开始运行")

max_wait_time = 300  # 5分钟
data_collection_results = {}

data_dir=os.path.join(os.getcwd(),'data')
log_dir=os.path.join(data_dir,'log')
if not os.path.exists(data_dir):
   os.mkdir(data_dir)
   logger.info("创建文件夹："+data_dir)
else:
    try:
        shutil.rmtree(data_dir)
        os.mkdir(data_dir)
    except OSError as e:
       logger.error("删除 "+data_dir+" 出错,错误原因："+str(e))
       

if not os.path.exists(log_dir):
   os.mkdir(log_dir)
   logger.info("创建文件夹："+data_dir)





# Maintain a list of clients (browsers) to send updates
clients=[]

def get_num(e):
  return e.get('value')

def run_command(command):
    print(command)
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    print(result.stdout)

def get_value(findstr,list):
    ll=[]
    for i in range(len(list)):
      if findstr in list[i]:
        if list[i][1] is not None:
          ll.append(list[i][1])
    if len(ll)==1:
      return ll[0]
    else:
      return ll
      

# def logging_finished(fname,end_flag):    
#     if os.path.isfile(fname):    
#       with open(fname) as file:
#         if len(file.readlines())>0:
#           lastline=file.readlines()[-1:]
#           if end_flag in lastline:
#               file.close()
#               return True
#         else:
#           return False
#     else:
#       return False

def file_search(dir,prefix,surfix):
  find_flag=False
  files=os.listdir(dir)
  for file in files:
    if file.startswith(prefix) and file.endswith(surfix):
      find_flag=True
      return file
  if not find_flag:
    return find_flag
    

def BuildClusterInventoryTree():
    hosts=[]
    clusters=[]
    cluster={}
    cluster_file=file_search(data_dir,'cluster-','.json')
    with open(cluster_file,'r') as f:
      data=json.load(f)
    f.close
    for dic in data:    
      cluster['name']=dic["name"]
      cluster['type']="cluster"  
      for i in dic['hosts']:      
        host={}
        host['name']=i
        host['type']="host"
        host['children']=[]
        hosts.append(host)
      cluster['children']=hosts
      clusters.append(cluster)
    return clusters
    

def BuildInventoryTree():
  dc={}
  dc_children=[]
  inventory_tree=[]
  # print("Check dc file exists")
  
  dc_file=file_search(data_dir,'dc-','.json')
  with open(dc_file,'r') as f:
    data=json.load(f)
  f.close
    # print(data)+
  for dic in data:
    dc['name']=dic['name']
    dc['type']="datacenter"
    
    for cluster_name in dic['sub_clusters']:
      for i in BuildClusterInventoryTree():
        if i['name']==cluster_name:
          dc_children.append(i)
    dc['children']=dc_children

    inventory_tree.append(dc)
  
  return inventory_tree


@app.template_global()
def static_include(filename):
    fullpath = os.path.join(app.static_folder, filename)
    with open(fullpath, 'r') as f:
        return f.read()
    



def data_collection_task(scriptname,vchost, vcuser, vcpassword, result_key):
    command = f"{python_path} {scriptname} {vchost} {vcuser} {vcpassword}"
    try:
        result = run_command(command)
        data_collection_results[result_key] = result
    except Exception as e:
        data_collection_results[result_key] = str(e)

@app.route('/', methods=['GET','POST'])
def index():
  if request.method == 'POST':
    # print(request.form)
    form_data=request.form.items()
    form_data_list = [[key, value] for key, value in form_data]
    

    vchost = request.form.get('vchost')
    vcuser = request.form.get('vcuser')
    vcpassword = request.form.get('vc_password')
    vcsa = request.form.get('vcsa')
    vcrootpassword = request.form.get('vcrootpassword')
    add_ipmi_host = request.form.get('add_ipmi_host')

    #获取VCSA 虚拟机内部信息，文件系统使用情况、证书等
    if vcsa =='on':
      cmd=f"{python_path} QueryVCSAInfo.py {vchost} {vcrootpassword}"
      logger.info("运行脚本："+f"{python_path} QueryVCSAInfo.py {vchost}")
      run_command(cmd)

    #获取Dell服务器的IPMI日志
    current_time=datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    ipmi_file=os.path.join(os.getcwd(),"ipmi-"+current_time+".log")
    if add_ipmi_host=='on':
      ipmihost_list=get_value('ipmiip',form_data_list)
      ipmiuser_list=get_value('ipmiuser',form_data_list)
      ipmipass_list=get_value('ipmipass',form_data_list)

      for i in range(len(ipmihost_list)):
        # cmd = ["python", "DellPowerEdgeQuery.py", ipmihost_list[i],ipmiuser_list[i],ipmipass_list[i]]
        cmd = f"{python_path} DellPowerEdgeQuery.py {ipmihost_list[i]} {ipmiuser_list[i]} {ipmipass_list[i]} {ipmi_file}"
        logger.info("运行脚本："+f"{python_path} DellPowerEdgeQuery.py {ipmihost_list[i]} {ipmiuser_list[i]} {ipmi_file}")
        run_command(cmd)


    cmd=f"{python_path} QueryAlarmInfo.py {vchost} {vcuser} {vcpassword}"
    run_command(cmd)



    #利用多进程发起信息收集任务
    cmd=f"{python_path} QueryHostInfo.py {vchost} {vcuser} {vcpassword}"
    logger.info(f"运行脚本： QueryHostInfo.py {vchost} {vcuser} ")
    run_command(cmd)

    cmd=f"{python_path} QueryClusterInfo.py {vchost} {vcuser} {vcpassword}"
    logger.info(f"运行脚本： QueryClusterInfo.py {vchost} {vcuser}")
    run_command(cmd)

    cmd=f"{python_path} QueryDCInfo.py {vchost} {vcuser} {vcpassword}"
    logger.info(f"运行脚本： QueryDCInfo.py {vchost} {vcuser}")
    run_command(cmd)

    cmd=f"{python_path} QueryVMInfo.py {vchost} {vcuser} {vcpassword}"
    logger.info(f"运行脚本： QueryVMInfo.py {vchost} {vcuser}")
    run_command(cmd)
    processes = []
    scriptname="QueryAlarmInfo.py"
    process = multiprocessing.Process(target=data_collection_task, args=(scriptname,vchost, vcuser, vcpassword, 'alarm_info'))
    process.start()
    processes.append(process)

    scriptname="QueryVMInfo.py"
    process = multiprocessing.Process(target=data_collection_task, args=(scriptname,vchost, vcuser, vcpassword, 'vms_info'))
    process.start()
    processes.append(process)

    scriptname="QueryHostInfo.py"
    process = multiprocessing.Process(target=data_collection_task, args=(scriptname,vchost, vcuser, vcpassword, 'hosts_info'))
    process.start()
    processes.append(process)

    scriptname="QueryClusterInfo.py"
    process = multiprocessing.Process(target=data_collection_task, args=(scriptname,vchost, vcuser, vcpassword, 'cluster_info'))
    process.start()
    processes.append(process)

    scriptname="QueryDCInfo.py"
    process = multiprocessing.Process(target=data_collection_task, args=(scriptname,vchost, vcuser, vcpassword, 'datacenter_info'))
    process.start()
    processes.append(process)

    for process in processes:
        process.join()
    return redirect(url_for('datacenter'))

  return render_template('login.html')
  


@app.route('/check_updates')
def check_updates():
    latest_updates=[]
    log_file_name = request.args.get('log')

    if os.path.exists(log_file_name):
      # Read the specified log file and return its content
      with open(log_file_name, 'r') as log_file:
          latest_updates = log_file.read()    
    else:
       latest_updates.append("该项信息收集未开始")  
    return latest_updates



def log_stream():
    #轮询检查各个信息收集脚本的生成的日志文件，读取更新进展日志，并按照类别进行输出
    log_dir=os.path.join(os.getcwd(),'data','log')
    vms_log_path=os.path.join(log_dir,"vmsInfo_gathering.log")
    hosts_log_path=os.path.join(log_dir,"hostsInfo_gathering.log")
    cluster_log_path=os.path.join(log_dir,"clusterInfo_gathering.log")
    dc_log_path=os.path.join(log_dir,"DCInfo_gathering.log")
    vcsa_log_path=os.path.join(log_dir,"vcsaInfo_gathering.log")
    log_files_path=[vms_log_path,hosts_log_path,cluster_log_path,dc_log_path,vcsa_log_path]
    

    vm_log_end_flag='the information acquisition of virtual machine(s) is finished!'
    host_log_end_flag='the information acquisition of ESXi host(s) is finished!'
    cluster_log_end_flag='the information acquisition of cluster(s) is finished!'    
    dc_log_end_flag='the information acquisition of datacenter(s) is finished!'
    vcsa_log_end_flag='the information acquisition of vcsa is finished!'
    log_end_flags=[vm_log_end_flag,host_log_end_flag,cluster_log_end_flag,dc_log_end_flag,vcsa_log_end_flag]

    eventType=['VM','HOST','CLUSTER','DATACENTER','VCSA']

    #收集结束标识
    subs_end=[[key,False] for key in ['vm_end','host_end','cluster_end','datacenter_end','vcsa_end']]
    all_end=False


    while not all_end:
        time.sleep(10)
        for i in range(len(log_files_path)):
            file=log_files_path[i]
            end_flag=log_end_flags[i]
            if os.path.exists(file):
                with open(file) as f:
                    # print(f)
                    lines=f.read().splitlines()   
                    #event：表示事件的类别，data：需要传递给客户端的事件信息              
                    yield f"event:{eventType[i]}\ndata:{lines}\n\n"
                    if len(lines)>0:
                      lastline=lines[-1]
                      if end_flag in lastline:
                          subs_end[i][1]=True
                f.close()

            else:
               print("日志文件："+file+ " 还未生成！")
        
        for sub_end in subs_end:
            all_end=True and sub_end[1]
            

        # print(log_updates)    
        # for update in log_updates:
        #     yield f"event:{update['eventType']}\ndata: {update['data'][0]}\n\n"
        #     # yield f"data: {update['data'][0]}\n\n"

@app.route('/progress')
def sse():
  # Add the client (browser) to the clients list
  # clients.append(request.environ['wsgi.input'])
  return Response(log_stream(),content_type='text/event-stream')



@app.route('/datacenter')
def datacenter():
  vcsa_file=file_search(data_dir,'vcsa-','.log')
  with open(vcsa_file,'r') as f:
    data=f.readlines()
  f.close()

  alarm_file=file_search(data_dir,'alarm-','.json')
  with open(alarm_file,'r') as f:
    alarm_list=json.load(f)
  f.close()

  df=False
  cert=False
  line_num=len(data)

  df_lines=[]
  cert_lines=[]
  for line in data:
      dfstart=re.search('df -h',line)
      if dfstart:
          df=True
          continue
      certstart=re.search(']#',line)
      if certstart:
          cert=True
          df=False
          continue
      if df:
          if len(line.strip())>0:
              rx=re.search('Filesystem',line)
              if not rx:        #drop the tile line
                  df_lines.append(line)
      if cert:
          rx=re.search('grep',line)
          if not rx:    #drop the first line
              cert_lines.append(line)

  vcsa_info=[]
  for line in df_lines:
    rx=re.search('(?P<filesystem>\S+)\s+(?P<size>\S+)\s+(?P<used>\S+)\s+(?P<avail>\S+)\s+(?P<use_perct>\S+)\s+(?P<mounton>\S+)\s+',line)
    if rx:
      fs_line={}
      fs_line['filesystem']=rx.group('filesystem')
      fs_line['size']=rx.group('size')
      fs_line['used']=rx.group('used')
      fs_line['avail']=rx.group('avail')
      fs_line['use_perct']=rx.group('use_perct')
      fs_line['mounton']=rx.group('mounton')
      vcsa_info.append(fs_line)

  vcsa_certs_info=[]
  certs_info_dict={}
  for line in cert_lines:   
      rx=re.search('Store :\s+',line)
      if rx: 
          if not certs_info_dict.get('storename'):
              certs_info_dict['storename']=line.split(":")[1].strip()
          else:  #部分只有store，没有alias和 not after行
              certs_info_dict['alias']=""
              certs_info_dict['expiration_time']=""
              vcsa_certs_info.append(certs_info_dict)
              certs_info_dict={}
              certs_info_dict['storename']=line.split(":")[1].strip()
      rx=re.search('Alias.*:',line)
      if rx:
          certs_info_dict['alias']=line.split(":")[1].strip()

      rx=re.search('Not After.*:\s+(?P<expiration_time>.*)',line)
      if rx:
          format_string = "%b  %d %H:%M:%S %Y %Z"        
          expiration_time=datetime.datetime.strptime(rx.group('expiration_time'),format_string)
          certs_info_dict['expiration_time']=expiration_time
          vcsa_certs_info.append(certs_info_dict)
          certs_info_dict={}

  for cert_info in vcsa_certs_info:
    if isinstance(cert_info['expiration_time'],datetime.datetime):
      if (cert_info['expiration_time']-datetime.datetime.utcnow()).days<90:
          cert_info['expirating']="Y"
      else:
          cert_info['expirating']="N"
  return render_template('datacenter.html', tree=BuildInventoryTree(),vcsa_fs=vcsa_info,vcsa_certs_info=vcsa_certs_info,alarm_list=alarm_list)



@app.route('/cluster')
@app.route('/cluster/<clustername>')
def cluster(clustername=None):
    hosts_info=[]
    cluster_config_dict={}
    clusters_config=[]


    host_file=file_search(data_dir,'hosts-','.json')
    with open(host_file,'r') as f:
      data=json.load(f)
    f.close

    for item in data:        
        item.pop("network_metrics")  #删除多余信息，减少数据传输
        item.pop("CPU_disk_metrics") #删除多余信息，减少数据传输
        item.pop("certificate")
        hosts_info.append(item)

    cluster_file=file_search(data_dir,'cluster-','.json')
    with open(cluster_file,) as f:
      data=json.load(f)
    f.close

    clusterHostMap=[]
    cluster_tree={}
    for cls in data:
      cluster_tree['name']=cls['name']
      cluster_tree['type']="cluster"
      cluster_tree['children']=[]
      for esxihost in cls['hosts']:
        child={}
        child['name']=esxihost
        child['type']="host"
        child['Children']=[]
        cluster_tree['children'].append(child)
      clusterHostMap.append(cluster_tree)


      for dic in data: 
        cluster_config_dict['name']=dic["name"]
        cluster_config_dict['ha_config']=dic['ha_config']
        cluster_config_dict['drs_config']=dic['drs_config']
        cluster_config_dict['evc_config']=dic['evc_config']
        
        vsan_info=dic['vsan_info']
        if len(vsan_info)>0:
          cluster_config_dict['vsan_enabled']=True
          cluster_config_dict['vsan_info']=vsan_info

        # clusters.append(cluster)
        clusters_config.append(cluster_config_dict)



    vsanHealthTest=[]
    cluster_disMapInfo=[]
    cluster_diskSmartStat=[]
    vsan_perf=[]


    vsanLogicalCapacity=vsanLogicalCapacityUsed=0
    vsanPhysicalCapacity=vsanPhysicalCapacityUsed=0
    vsanDedupMetadataSize=vsanCompressionMetadataSize=0
    for item in vsan_info:
      if item.get("health_test"):
        vsanHealthTest=item.get("health_test")
      if item.get("cluster_disMapInfo"):
        cluster_disMapInfo=item.get("cluster_disMapInfo")
      if item.get("cluster_diskSmartStat"):
        cluster_diskSmartStat=item.get("cluster_diskSmartStat")
      if item.get("vsan_perf"):
        vsan_perf=item.get("vsan_perf")
      if item.get("logicalCapacity"):
        vsanLogicalCapacity=item.get("logicalCapacity")
        vsanLogicalCapacity=Decimal(vsanLogicalCapacity/1024/1024/1024).quantize(Decimal("0"))
      if item.get("logicalCapacityUsed"):
        vsanLogicalCapacityUsed=item.get("logicalCapacityUsed")
        vsanLogicalCapacityUsed=Decimal(vsanLogicalCapacityUsed/1024/1024/1024).quantize(Decimal("0"))
      if item.get("physicalCapacity"):
        vsanPhysicalCapacity=item.get("physicalCapacity")
        vsanPhysicalCapacity=Decimal(vsanPhysicalCapacity/1024/1024/1024).quantize(Decimal("0"))
      if item.get("physicalCapacityUsed"):
        vsanPhysicalCapacityUsed=item.get("physicalCapacityUsed") 
        vsanPhysicalCapacityUsed=Decimal(vsanPhysicalCapacityUsed/1024/1024/1024).quantize(Decimal("0"))
      if item.get("dedupMetadataSize"):
        vsanDedupMetadataSize=item.get("dedupMetadataSize") 
        vsanDedupMetadataSize=Decimal(vsanDedupMetadataSize/1024/1024/1024).quantize(Decimal("0"))
      if item.get("compressionMetadataSize"):
        vsanCompressionMetadataSize=item.get("compressionMetadataSize")
        vsanCompressionMetadataSize=Decimal(vsanCompressionMetadataSize/1024/1024/1024).quantize(Decimal("0"))


    if clustername is not None:
      for clsCfg in clusters_config:
        if clsCfg['name']==clustername:
          health_group_data=defaultdict(list)
          for item_info in clsCfg['vsan_info']:   
            if item_info.get('health_test'): 
              for test in item_info['health_test']:        
                group_name=test["groupName"]
                health_group_data[group_name].append(test)

          return render_template('cluster.html', host_detail=hosts_info, \
                                clusterHostMap=clusterHostMap,\
                                  cluster_config=clsCfg,\
                                  health_group_data=health_group_data,\
                                  cluster_disMapInfo=cluster_disMapInfo,\
                                  cluster_diskSmartStat=cluster_diskSmartStat,\
                                  vsan_perf=vsan_perf,\
                                  vsanLogicalCapacity=vsanLogicalCapacity,\
                                  vsanLogicalCapacityUsed=vsanLogicalCapacityUsed,\
                                  vsanPhysicalCapacity=vsanPhysicalCapacity,\
                                  vsanPhysicalCapacityUsed=vsanPhysicalCapacityUsed,\
                                  vsanDedupMetadataSize=vsanDedupMetadataSize, \
                                  vsanCompressionMetadataSize=vsanCompressionMetadataSize,\
                                  tree=BuildInventoryTree())


@app.route('/host')
@app.route('/host/<name>')
def host(name=None):
  vms_inventory=[]
  vms_file=file_search(data_dir,'vms-','.json')
  with open(vms_file,'r') as f:
    data=json.load(f)
  f.close
  for dic in data:
    vm={}
    vm['name']=dic['Display_name']
    vm['uuid']=dic['uuid']
    vm['host']=dic['esxihostname']
    vm['powerState']=dic['powerState']
    vm['type']="virtualmachine"
    vms_inventory.append(vm) 
  
  

  host_detail=[]
  host_file=file_search(data_dir,'hosts-','.json')
  with open(host_file,'r') as f:
    data=json.load(f)
  f.close
  if name is not None:
    for item in data:
      if item['host']==name:
        host_detail.append(item)
    return render_template('host.html', host_detail=host_detail,host_vms=vms_inventory,tree=BuildInventoryTree())
  

@app.route('/virtualmachine')
def vms_summary():
  vms_file=file_search(data_dir,'vms-','.json')
  with open(vms_file,) as f:
    data=json.load(f)
  f.close
  vms_total_num=len(data)
  vms_powerOn_num=0
  vms_powerOff_num=0
  tools_outdate=0
  tools_up2date=0
  tools_notInstalled=0
  tools_Unmanaged=0
  vm_tools_list=[]

  total_provisioned_disk=0
  total_used_disk=0
  total_snap_disk=0
  top10_vCPU_list=[0,0,0,0,0,0,0,0,0,0]
  top10_RAM_list=[0,0,0,0,0,0,0,0,0,0]
  top10_pro_disk_list=[0,0,0,0,0,0,0,0,0,0]
  top10_used_disk_list=[0,0,0,0,0,0,0,0,0,0]
  top10_snap_disk_list=[0,0,0,0,0,0,0,0,0,0]
  vms_guest_os_stastic_list=[]
  
  vms_vCPU=[]
  vms_top10_vCPU=[]
  
  vms_mem=[]
  vms_top10_mem=[]
  
  vms_Provisioned_diskSize=[]
  vms_top10_Provisioned_diskSize=[]

  vms_Used_diskSize=[]
  vms_top10_Used_diskSize=[]

  vms_snapshotSize=[]
  vms_top10_snapshotSize=[]
  
  for vm in data:
    if vm['powerState']=="poweredOn":
      vms_powerOn_num+=1
    else:
      vms_powerOff_num+=1
    
    find_os=False
    vms_guest_os_stastic_dict={}
    for dict in vms_guest_os_stastic_list:
      if vm['config_guestFullName'] in dict.values():
        dict['value']+=1
        find_os=True
    if find_os==False :
      vms_guest_os_stastic_dict['name']=vm['config_guestFullName']
      vms_guest_os_stastic_dict['value']=1
      vms_guest_os_stastic_list.append(vms_guest_os_stastic_dict)
    vms_guest_os_stastic_list.sort(key=get_num)


    version_exist=False
    vm_tools_dict={}
    for dict in vm_tools_list:
      if vm['toolsVersion'] in dict.values():
        dict['value']+=1
        version_exist=True
    if version_exist==False:
      vm_tools_dict['name']=vm['toolsVersion']
      if vm_tools_dict['name']==0:
        vm_tools_dict['name']="NotInstalled"
      if vm_tools_dict['name']==2147483647:
        vm_tools_dict['name']="Unmanaged"
      vm_tools_dict['value']=1
      vm_tools_list.append(vm_tools_dict)
    if vm['tools_status']=='Current':
      tools_up2date+=1
    elif vm['tools_status']=='NotInstalled':
      tools_notInstalled+=1
    elif vm['tools_status']=='Unmanaged':
      tools_Unmanaged+=1
    else:
      tools_outdate+=1
    vm_tools_list.sort(key=get_num)
    # print(vm_tools_list)

    vCPU_num=vm['numCPU']
    vm_cpu_num={}
    for i in range(10): #列表长度为10
      if vCPU_num>=top10_vCPU_list[i]:
        top10_vCPU_list.pop(0) #删除最小的元素
        top10_vCPU_list.append(vCPU_num) #将新的值添加到列表
        top10_vCPU_list.sort()            
        vm_cpu_num['name']=vm['Display_name']
        vm_cpu_num['value']=vm['numCPU']
        vms_vCPU.append(vm_cpu_num)
        break
      if vCPU_num>=top10_vCPU_list[i]:        
        vm_cpu_num['name']=vm['Display_name']
        vm_cpu_num['value']=vm['numCPU']
        vms_vCPU.append(vm_cpu_num)
        break
    vms_vCPU.sort(key=get_num)
    
  
    RAM_num=vm['memoryMB']
    vm_ram_num={}
    for i in range(10):
      if RAM_num>=top10_RAM_list[i]:
        top10_RAM_list.pop(0)
        top10_RAM_list.append(RAM_num)
        top10_RAM_list.sort()
        vm_ram_num['name']=vm['Display_name']
        vm_ram_num['value']=vm['memoryMB']
        vms_mem.append(vm_ram_num)
        break
      if RAM_num==top10_RAM_list[i]:
        vm_ram_num['name']=vm['Display_name']
        vm_ram_num['value']=vm['memoryMB']
        vms_mem.append(vm_ram_num)
        break
    vms_mem.sort(key=get_num)

    
    total_provisioned_disk=0
    total_used_disk=0
    total_snap_disk=0
    
    for disk in vm['disks_info']:
      if disk.get("provisioned_disk_size"): #VDI有磁盘不存在provisioned_disk属性
        total_provisioned_disk+=disk["provisioned_disk_size"]  
      total_used_disk+=disk["used_disk_size"]
      total_snap_disk+=disk["disk_snap_size"]
    # print("-----")
    # print("Total Provisioned disk: {}".format(total_provisioned_disk))
    # print("Totaol used disk: {}".format(total_provisioned_disk))
    # print("Totaol snapshot disk: {}".format(total_provisioned_disk))


    vm_pro_disk_size={}
    
    
    for i in range(10):
      if total_provisioned_disk>top10_pro_disk_list[i]:
        top10_pro_disk_list.pop(0)
        top10_pro_disk_list.append(total_provisioned_disk)
        top10_pro_disk_list.sort()
        # print("top10_pro_disk_list: {}".format(top10_pro_disk_list))
        vm_pro_disk_size['name']=vm['Display_name']
        vm_pro_disk_size['value']=total_provisioned_disk
        vms_Provisioned_diskSize.append(vm_pro_disk_size)
        # print("vm_disk_size: {}".format(vm_pro_disk_size))
        # print("vms_Provisioned_diskSize: {}".format(vms_Provisioned_diskSize))
        break
      elif total_provisioned_disk==top10_pro_disk_list[i]:
        vm_pro_disk_size['name']=vm['Display_name']
        vm_pro_disk_size['value']=total_provisioned_disk
        vms_Provisioned_diskSize.append(vm_pro_disk_size)
        break

    vms_Provisioned_diskSize.sort(key=get_num)
    # print("top10_pro_disk_list: {}".format(top10_pro_disk_list))
    # print("vms_Provisioned_diskSize: {}".format(vms_Provisioned_diskSize))
    
    vm_used_disk_size={}
    for i in range(10):
      if total_used_disk>top10_used_disk_list[i]:
        top10_used_disk_list.pop(0)
        top10_used_disk_list.append(total_used_disk)
        top10_used_disk_list.sort()
        vm_used_disk_size['name']=vm['Display_name']
        vm_used_disk_size['value']=total_used_disk
        vms_Used_diskSize.append(vm_used_disk_size)
        break
      elif total_used_disk==top10_used_disk_list[i]:
        vm_used_disk_size['name']=vm['Display_name']
        vm_used_disk_size['value']=total_used_disk
        vms_Used_diskSize.append(vm_used_disk_size)
        break        

    vms_Used_diskSize.sort(key=get_num)



    vm_snap_disk_size={}
    for i in range(10):
      if total_snap_disk>top10_snap_disk_list[i]:
        top10_snap_disk_list.pop(0)
        top10_snap_disk_list.append(total_snap_disk)
        top10_snap_disk_list.sort()
        vm_snap_disk_size['name']=vm['Display_name']
        vm_snap_disk_size['value']=total_snap_disk
        vms_snapshotSize.append(vm_snap_disk_size)
        break
      if total_snap_disk==top10_snap_disk_list[i]:
        vm_snap_disk_size['name']=vm['Display_name']
        vm_snap_disk_size['value']=total_snap_disk
        vms_snapshotSize.append(vm_snap_disk_size)
        break
    vms_snapshotSize.sort(key=get_num)



  for item in vms_vCPU:
    if item['value'] in top10_vCPU_list:
      vms_top10_vCPU.append(item)
  if len(vms_top10_vCPU)>=15:
    vms_top10_vCPU=vms_top10_vCPU[-15::]

  for item in vms_mem:
    if item['value'] in top10_RAM_list:
      vms_top10_mem.append(item)

  for item in vms_Used_diskSize:
    if item['value'] in top10_used_disk_list:
      vms_top10_Used_diskSize.append(item)
  
  for item in vms_Provisioned_diskSize:
    if item['value'] in top10_pro_disk_list:
      vms_top10_Provisioned_diskSize.append(item)

  for item in vms_snapshotSize:
    if item['value'] in top10_snap_disk_list:
      vms_top10_snapshotSize.append(item)
  
  return render_template('vms_summary.html',vms_top10_snapshotSize=vms_top10_snapshotSize,vms_top10_Used_diskSize=vms_top10_Used_diskSize, \
                        vms_top10_Provisioned_diskSize=vms_top10_Provisioned_diskSize, \
                        vms_top10_mem=vms_top10_mem,\
                        vms_top10_vCPU=vms_top10_vCPU,\
                        vms_guest_os_stastic_list=vms_guest_os_stastic_list, \
                        vms_powerOn_num=vms_powerOn_num, \
                        vms_powerOff_num=vms_powerOff_num,\
                        vm_tools_list=vm_tools_list,\
                        tools_outdate=tools_outdate, \
                        tools_up2date=tools_up2date,\
                        tools_notInstalled=tools_notInstalled,\
                        tools_Unmanaged=tools_Unmanaged
                        )


@app.route('/virtualmachine/<vm_name>')
def virtualmachine(vm_name=None):
  vms_file=file_search(data_dir,'vms-','.json')
  with open(vms_file,) as f:
    data=json.load(f)
  f.close
  vm_info=[]
  vm_perf_metric=[]
  for vm in data:
    if vm['Display_name']==vm_name:
      vm_info.append(vm)
      vm_perf_metric=vm["vm_perf_metric"]
  return render_template('virtualmachine.html',tree=BuildInventoryTree(),vm_info=vm_info,vm_perf_metric=vm_perf_metric)



if __name__=='__main__':
    app.run(debug=True,port=5000)
    multiprocessing.freeze_support()  