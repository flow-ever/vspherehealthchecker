import time,datetime
import os
import multiprocessing 
import sys
import re
import json
# from decimal import Decimal
import logging
import requests
from QueryVCSAInfo import QueryVCSAInfo
from QueryAlarmInfo import QueryAlarmInfo
from QueryDCInfo import QueryDCsInfo
from QueryVMInfo import QueryVMsInfo
from DellPowerEdgeQuery import QueryiDRAC


from flask import Flask,render_template,request,Response,redirect,url_for

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
# script_directory = os.path.dirname(sys.argv[0])

# python_path=os.path.join(script_directory, 'python.exe')
python_path=sys.executable



logger.info(app.name+" 开始运行")


data_dir=os.path.join(os.getcwd(),'data')
log_dir=os.path.join(data_dir,'log')
if not os.path.exists(data_dir):
   os.mkdir(data_dir)
   logger.info("创建文件夹："+data_dir)
# else:
#     try:
#         shutil.rmtree(data_dir)
#         os.mkdir(data_dir)
#     except OSError as e:
#        logger.error("删除 "+data_dir+" 出错,错误原因："+str(e))
       

if not os.path.exists(log_dir):
   os.mkdir(log_dir)
   logger.info("创建文件夹："+data_dir)






def get_num(e):
  return e.get('value')

def log_subprocess_output(pipe):
    for line in iter(pipe.readline, b''):  # b'\n'-separated lines
        print(repr(line))
        logger.info(line.decode('utf-8',errors='ignore').strip())


def get_value(findstr,strlist):
    ll=[]
    for i in range(len(strlist)):
      rx=re.search(findstr,"".join(strlist[i]))
      if rx and strlist[i][1] is not None:
          ll.append(strlist[i][1])
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
  file_list=[]
  find_flag=False
  files=os.listdir(dir)
  for file in files:
    if file.startswith(prefix) and file.endswith(surfix):
      find_flag=True
      file_list.append(os.path.join(dir,file))
  if not find_flag:
    return find_flag
  else:
     return file_list
    

    
#构建整个vcenter的树状清单
def BuildInventoryTree():  
  dc_file=file_search(data_dir,'dc-','.json')
  if len(dc_file)==1:
    with open(dc_file[0],'r') as f:
      vcenter_data=json.load(f)
    f.close
  
  inventory_tree=[]
  
  for vc in vcenter_data:
      vcenter={}
      vcenter['name']=vc['name']
      vcenter['path']=vc['id']
      vcenter['children']=[]

  
      for dc in vc['datacenters']:
          dc_tree={} 
          clusters=[]   
          
          dc_tree['name']=dc['name']
          dc_tree['path']=dc['parent']+'-'+dc['id']
          
          if len(dc['clusters'])>0:          
              for cls in dc['clusters']:
                  cluster={}
                  cluster['name']=cls['name']
                  cluster['path']=dc_tree['path']+'-'+cls['id']
                  hosts=[]
                  if len(cls['hosts'])>0:
                      for item in cls['hosts']:
                          host={}
                          host['name']=item['name']
                          host['path']=cluster['path']+'-'+item['id']
                          host['children']=[]
                          hosts.append(host)
                      cluster['children']=hosts            
                  else:               
                      cluster['children']=[]
                  # cluster['children']=cls['hosts']
                  clusters.append(cluster)          
              dc_tree['children']=clusters         
          else:
              dc_tree['children']=[]
          vcenter['children'].append(dc_tree)
      inventory_tree.append(vcenter)
  return inventory_tree

#构建整个指定的数据中心（datacenter）的主机、虚拟机树状清单
def BuildDCHostInventoryTree(dc_id:str):  
  dc_file=file_search(data_dir,'dc-','.json')
  if len(dc_file)==1:
    with open(dc_file[0],'r') as f:
      vcenter_data=json.load(f)
    f.close
  
  inventory_tree=[]
  for vc in vcenter_data:
    vcenter={}
    vcenter['name']=vc['name']
    vcenter['path']=vc['id']
    vcenter['type']=vc['type']
    vcenter['children']=[]

    
    for dc in vc['datacenters']:
        dc_tree={} 
        clusters=[]   
        
        dc_tree['name']=dc['name']
        dc_tree['type']=dc['type']
        dc_tree['path']=dc['parent']+'-'+dc['id']
        if dc_tree['path']==dc_id:        
          if len(dc['clusters'])>0:          
              for cls in dc['clusters']:
                  cluster={}
                  cluster['name']=cls['name']
                  cluster['path']=cls['path']
                  cluster['type']=cls['type']
                  hosts=[]
                  if len(cls['hosts'])>0:
                      for item in cls['hosts']:
                          host={}
                          host['name']=item['name']
                          host['path']=item['path']
                          host['type']='host'
                          host['children']=[]
                          for v in item['vm_list']:
                              vm={}
                              vm['name']=v['name']
                              vm['path']=v['path']
                              vm['type']='vm'
                              vm['children']=[]
                              host['children'].append(vm)
                          hosts.append(host)
                      cluster['children']=hosts            
                  else:               
                      cluster['children']=[]
                  # cluster['children']=cls['hosts']
                  clusters.append(cluster)          
              dc_tree['children']=clusters         
          else:
              dc_tree['children']=[]
          inventory_tree.append(dc_tree)
          break
          
  return inventory_tree

#从vms-xxx.json生成虚拟机网络信息文件vms-xxxx-network.json
def create_vm_network_info(vms_file:str):
  if len(vms_file)>0:
    with open(vms_file,'r') as f:
      vm_data=json.load(f)
    f.close()

    vms=[]
    
    for vm in vm_data:
      vm_network={}
      vm_network['Display_name']=vm['Display_name']  
      vm_network['vnics']=vm['vnics']
      vms.append(vm_network)
    rx=re.search('vms-(?P<time_stamp>\d+).json',vms_file)
    vms_network_file=os.path.join(data_dir,'vms_network-'+rx.group('time_stamp')+'.json')
    if os.path.exists(vms_network_file):
      return vms_network_file
    else:
      with open(vms_network_file,'w') as f:
        json.dump(vms,f,indent=4,ensure_ascii=False,default=str,cls=MyEncoder)
      f.close()    
      return vms_network_file


#构建整个指定的数据中心（datacenter）的网络结构树状清单
def BuildDCNetworkInventoryTree(dc_id:str):    
  dc_file=file_search(data_dir,'dc-','.json')
  if len(dc_file)==1:
    with open(dc_file[0],'r') as f:
      vcenter_data=json.load(f)
    f.close()

  vm_file=file_search(data_dir,'vms-','.json')
  
  if vm_file:
    if len(vm_file)==1:
      vm_network_file=create_vm_network_info(vm_file[0])
      with open(vm_network_file) as f:
        vm_network_info=json.load(f)
      f.close()
  else:
     vm_network_info=""
  
  inventory_tree=[]
  for vc in vcenter_data:
    vcenter={}
    vcenter['name']=vc['name']
    vcenter['path']=vc['id']
    vcenter['type']=vc['type']
    vcenter['children']=[]

    
    for dc in vc['datacenters']:
        dc_tree={} 
        vdss=[]   
        
        dc_tree['name']=dc['name']
        dc_tree['type']=dc['type']
        dc_tree['path']=dc['parent']+'-'+dc['id']
        if dc_tree['path']==dc_id:        
          if len(dc['dvs'])>0:   
                     
              for vs in dc['dvs']:
                  vds={}
                  vds['name']=vs['name']
                  vds['path']=vs['path']
                  vds['type']=vs['type']
                  vds['children']=[]
                  portgroups=[]
                  if len(vs['portgroups'])>0:
                      for item in vs['portgroups']:
                          pg={}
                          pg['name']=item['name']
                          pg['path']=item['path']
                          pg['type']='portgroup'
                          pg['children']=[]
                          if len(vm_network_info)>0: 
                             for vm in vm_network_info:                                
                                for vnic in vm['vnics']:
                                  if vnic['portGroup']==pg['name']:
                                    vm_net={}
                                    vm_net['name']=vm['Display_name']
                                    print(vm['Display_name'])
                                    vm_net['type']='vm'
                                    vm_net['children']=[]
                                    
                                    pg['children'].append(vm_net)
                                    break

                                    


                          portgroups.append(pg)

                      vds['children']=portgroups            

                  vdss.append(vds)          
              dc_tree['children']=vdss         
          else:
              dc_tree['children']=[]
          inventory_tree.append(dc_tree)
          break
  # print(inventory_tree)        
  return inventory_tree



@app.template_global()
def static_include(filename):
    fullpath = os.path.join(app.static_folder, filename)
    with open(fullpath, 'r') as f:
        return f.read()
    
def check_url(url:str):
   x=requests.get(url,timeout=2)
   if x.status_code==200:
      return True
   else:
      return False




#数据收集首页，输入vcenter的SSO登录凭据以及vcsa虚拟机root用户密码等
@app.route('/', methods=['GET','POST'])
def index():
  if request.method=='GET':
     release=request.args.get('version',default="1.1",type=str)
     return render_template('login.html',release=release)

  if request.method == 'POST':
    # print(request.form)
    form_data=request.form.items()
    form_data_list = [[key, value] for key, value in form_data]


    vchost = request.form.get('vchost')
    vcuser = request.form.get('vcuser')
    vcpassword = request.form.get('vc_password')
    # vcsa = request.form.get('vcsa')
    vcrootpassword = request.form.get('vcrootpassword')
    add_ipmi_host = request.form.get('add_ipmi_host')
    process=multiprocessing.Process

    # #获取VCSA 虚拟机内部信息，文件系统使用情况、证书等
    p1=process(target=QueryVCSAInfo,args=(vchost,vcrootpassword))  
    p2=process(target=QueryAlarmInfo,args=(vchost,vcuser,vcpassword))   
    p3=process(target=QueryDCsInfo,args=(vchost,vcuser,vcpassword))   
    p4=process(target=QueryVMsInfo,args=(vchost,vcuser,vcpassword))    

    p1.start()
    p2.start()
    p3.start()
    p4.start()

    p1.join()
    p2.join()
    p3.join()
    p4.join()
       
    if add_ipmi_host=='on':
      logger.info("IPMI信息收集开启")
      ipmihost_list=get_value('ipmiip',form_data_list)
      ipmiuser_list=get_value('ipmiuser',form_data_list)
      ipmipass_list=get_value('ipmipass',form_data_list)

      ipmi_ps=[]
      for i in range(len(ipmihost_list)):
        # cmd = ["python", "DellPowerEdgeQuery.py", ipmihost_list[i],ipmiuser_list[i],ipmipass_list[i]]
        # cmd = f"{python_path} DellPowerEdgeQuery.py {ipmihost_list[i]} {ipmiuser_list[i]} {ipmipass_list[i]} {ipmi_file}"
        # logger.info("运行脚本："+f"{python_path} DellPowerEdgeQuery.py {ipmihost_list[i]} {ipmiuser_list[i]} {ipmi_file}")
        # run_command(cmd)
        # cmd=('DellPowerEdgeQuery.py','QueryiDRAC',( ipmihost_list[i], ipmiuser_list[i],ipmipass_list[i]))
        ipmi_ps.append(process(target=QueryiDRAC,args=( ipmihost_list[i], ipmiuser_list[i],ipmipass_list[i])))
      for i in range(len(ipmi_ps)):
         ipmi_ps[i].start()
      
      for i in range(len(ipmi_ps)):
         ipmi_ps[i].join()

  

    return redirect(url_for('datacenter'))

  return redirect(url_for('index'))
  

def ipmi_data_merge():
   all_hosts_ipmi_data=[]
   host_ipmi_data=[]
   ipmi_merge_file=os.path.join(data_dir,'hosts_hardware_info.json')
   ipmi_files=file_search(data_dir,'ipmi','json')

   for file in ipmi_files:
      print(file)
      with open(file,'r') as f:
        host_ipmi_data=json.load(f)
      all_hosts_ipmi_data.append(host_ipmi_data[0])
   with open(ipmi_merge_file,'w') as f:
      json.dump(all_hosts_ipmi_data,f,indent=4,ensure_ascii=False,default=str) 
   f.close()
   return os.path.join(data_dir,ipmi_merge_file)

def show_ipmi_data(file):
   with open(file,'r') as f:
    data=json.load(f)
   f.close()
   


   return data






# @app.route('/check_updates')
# def check_updates():
#     latest_updates=[]
#     log_file_name = request.args.get('log')

#     if os.path.exists(log_file_name):
#       # Read the specified log file and return its content
#       with open(log_file_name, 'r') as log_file:
#           latest_updates = log_file.read()    
#     else:
#        latest_updates.append("该项信息收集未开始")  
#     return latest_updates


def gathering_progress(eventtype:str):
    log_dir=os.path.join(os.getcwd(),'data','log')
    vms_log_path=os.path.join(log_dir,"vmsInfo_gathering.log")
    ipmi_log_path=os.path.join(log_dir,"IPMIInfo_gathering.log")
    dc_log_path=os.path.join(log_dir,"DCInfo_gathering.log")
    vcsa_log_path=os.path.join(log_dir,"vcsaInfo_gathering.log")
    log_files_path=[vms_log_path,ipmi_log_path,dc_log_path,vcsa_log_path]
    

    vm_log_end_flag='the information acquisition of virtual machine(s) is finished!'
    ipmi_log_end_flag='the information acquisition of ipmi host(s) is finished!'    
    dc_log_end_flag='the information acquisition of datacenter(s) is finished!'
    vcsa_log_end_flag='the information acquisition of vcsa is finished!'
    log_end_flags=[vm_log_end_flag,ipmi_log_end_flag,dc_log_end_flag,vcsa_log_end_flag]

    eventType_list=['VM','IPMI','DATACENTER','VCSA']
    k=0
    for i in range(len(eventType_list)):
       if eventType_list[i]==eventtype:
          k=i
          break

    file_end=False
    while not file_end:
      if os.path.exists(log_files_path[k]):
          with open(log_files_path[k]) as f:
            lines=f.read().splitlines()
            #event：表示事件的类别，data：需要传递给客户端的事件信息              
            yield f"event:{'VM'}\ndata:{lines}\n\n"  
            if len(lines)>0:
              lastline=lines[-1]
              if log_end_flags[k] in lastline:
                  file_end=True   


#收集进度数据的函数
def log_stream():
    #轮询检查各个信息收集脚本的生成的日志文件，读取更新进展日志，并按照类别进行输出
    log_dir=os.path.join(os.getcwd(),'data','log')
    vms_log_path=os.path.join(log_dir,"vmsInfo_gathering.log")
    ipmi_log_path=os.path.join(log_dir,"IPMIInfo_gathering.log")
    dc_log_path=os.path.join(log_dir,"DCInfo_gathering.log")
    vcsa_log_path=os.path.join(log_dir,"vcsaInfo_gathering.log")
    log_files_path=[vms_log_path,ipmi_log_path,dc_log_path,vcsa_log_path]
    

    vm_log_end_flag='the information acquisition of virtual machine(s) is finished!'
    ipmi_log_end_flag='the information acquisition of ipmi host(s) is finished!'    
    dc_log_end_flag='the information acquisition of datacenter(s) is finished!'
    vcsa_log_end_flag='the information acquisition of vcsa is finished!'
    log_end_flags=[vm_log_end_flag,ipmi_log_end_flag,dc_log_end_flag,vcsa_log_end_flag]

    eventType=['VM','IPMI','DATACENTER','VCSA']

    #收集结束标识
    subs_end=[[key,False] for key in ['vm_end','ipmi_end','datacenter_end','vcsa_end']]
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

#将数据收集的进度数据发送到url /check_updates，浏览器客户端可以从该url获得数据，然后展现在前端页面
# @app.route('/progress/<string:eventtype>')
# def sse(eventtype):
#   # Add the client (browser) to the clients list
#   # clients.append(request.environ['wsgi.input'])
#   return Response(gathering_progress(eventtype),mimetype='text/event-stream')
@app.route('/progress')
def sse():
  # Add the client (browser) to the clients list
  # clients.append(request.environ['wsgi.input'])
  return Response(log_stream(),mimetype='text/event-stream')

def show_vcenter():
  vcsa_file=file_search(data_dir,'vcsa-','.log')
  # print(vcsa_file)
  if len(vcsa_file)==1:
    with open(vcsa_file[0],'r') as f:
      data=f.readlines()
    f.close()

  alarm_file=file_search(data_dir,'alarm-','.json')
  if len(alarm_file)==1:
    with open(alarm_file[0],'r') as f:
      alarm_list=json.load(f)
    f.close()
  alarm_acked=0
  alrm_noacked=0
  for alarm in alarm_list:
    if alarm['acknowledged']:
        alarm_acked+=1
    else:
        alrm_noacked+=1
  alarm_ack=[alarm_acked,alrm_noacked]

  df=False
  cert=False


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

  
  #获取服务列表
  service_dict={}
  for line in data:
      # vstats (VMware vStats Service)
      rx=re.search('(.*)\s*\((.*)\)',line.strip())
      if rx:
          service_dict[rx.group(1).strip()]=rx.group(2)

  #获取服务运行状态
  # Name: applmgmt
  # Starttype: AUTOMATIC
  # RunState: STARTED
  # RunAsUser: root
  # CurrentRunStateDuration(ms): 3518736438
  # HealthState: HEALTHY
  # FailStop: N/A
  # MainProcessId: 3534
  servicesStatus_list=[]
  find_flag=False
  i=0
  serviceStatus_dict={}
  for line in data:
      pattern_start='for i in \$\('
      pattern_end='mchage -l root'
      rx=re.search(pattern_end,line)
      if rx:
        find_flag=False    
      
      rx=re.search(pattern_start,line)
      if rx:
        find_flag=True        
        continue
      
      
      if find_flag:
        key=line.strip().split(':')[0]          
        if key in ['Name','Starttype','RunState','RunAsUser','CurrentRunStateDuration(ms)','FailStop','MainProcessId','HealthState']:
            value=line.strip().split(':')[1].strip()
            serviceStatus_dict[key]=value
            i+=1
            if i % 8 ==0:
              # print(serviceStatus_dict)
              servicesStatus_list.append(serviceStatus_dict)
              serviceStatus_dict={}
  for service_status in servicesStatus_list:
     if service_status['Name'] in service_dict.keys():
        service_status['full name']=service_dict[service_status['Name']]
  
  

  #root用户密码过期情况
  find_flag=False
  root_pass_lines=[]
  for line in data:
      rx=re.search(']#.*chage -l root',line)
      if rx:
          # print('find')
          find_flag=True
      if find_flag:
          root_pass_lines.append(line.strip())   

  root_pass_lines.pop(0) #删除首行（命令和命令提示符）
  root_pass_lines.pop() #删除尾行（命令提示符）
  null_str=''  #删除空行
  while (null_str in root_pass_lines):
      root_pass_lines.remove(null_str)
     

  cert_healthy_counter=0
  cert_expired_counter=0
  cert_expiring_counter=0
  for cert_info in vcsa_certs_info:
    if isinstance(cert_info['expiration_time'],datetime.datetime):
      if (cert_info['expiration_time']-datetime.datetime.utcnow()).days<90 and (cert_info['expiration_time']-datetime.datetime.utcnow()).days>0:
          cert_info['expirating']="Y"
          cert_expiring_counter+=1
      elif (cert_info['expiration_time']-datetime.datetime.utcnow()).days<=0:
        cert_info['expirated']="Y"
        cert_expired_counter+=1
      else:
          cert_info['expirating']="N"
          cert_healthy_counter+=1
  cert_status_counter=[cert_healthy_counter,cert_expiring_counter,cert_expired_counter]


  

  return [ 
          vcsa_info, 
          vcsa_certs_info,
          cert_status_counter, 
          servicesStatus_list, 
          root_pass_lines,                        
          alarm_list,
          alarm_ack ]


def show_datacenter(path_list:list):
    vcenter_id=path_list[0]
    datacenter_id=path_list[1]
    dc_file=file_search(data_dir,'dc-','.json')
    if len(dc_file)==1:
      with open(dc_file[0],) as f:
        vc_data=json.load(f)
      f.close

    dc_data={}

    for vc in vc_data:
       if vc['id']==vcenter_id:
          for dc in vc['datacenters']:
             if dc['id']==datacenter_id:
                dc_data=dc
    # return dc_data 
    dss=[]
    for item in dc_data['datastores']:
       ds={}
       ds['name']=item['name']
       ds['type']=item['type']
       ds['path']=item['path']
       


    inventory_id='-'.join(path_list)
    dc_tree=BuildDCHostInventoryTree(inventory_id)
    dc_network_tree=BuildDCNetworkInventoryTree(inventory_id)

    return [dc_tree,dc_data,dc_network_tree]


def show_cluster(path_list:list):
    vcenter_id=path_list[0]
    datacenter_id=path_list[1]
    cls_id=path_list[2]
    dc_file=file_search(data_dir,'dc-','.json')
    if len(dc_file)==1:
      with open(dc_file[0],) as f:
        vc_data=json.load(f)
      f.close

    cls_data={}

    for vc in vc_data:
       if vc['id']==vcenter_id:
          for dc in vc['datacenters']:
             if dc['id']==datacenter_id:
                for cls in dc['clusters']:
                   if cls['id']==cls_id:
                      cls_data=cls
    return cls_data                  


def show_host(path_list:list):
    vcenter_id=path_list[0]
    datacenter_id=path_list[1]
    cls_id=path_list[2]
    host_id=path_list[3]
    dc_file=file_search(data_dir,'dc-','.json')
    if len(dc_file)==1:
      with open(dc_file[0],) as f:
        vc_data=json.load(f)
      f.close

    host_data={}

    for vc in vc_data:
       if vc['id']==vcenter_id:
          for dc in vc['datacenters']:
             if dc['id']==datacenter_id:
                for cls in dc['clusters']:
                   if cls['id']==cls_id:
                      for host in cls['hosts']:
                         if host['id']==host_id:
                            host_data=host                      
    return host_data                          



# @app.route('/virtualmachine')
def show_VMSummary():
  vms_file=file_search(data_dir,'vms-','.json')
  if len(vms_file)==1:
    print(vms_file[0])
    with open(vms_file[0],) as f:
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

    

    total_used_disk=vm['TotalUsedSpace']
    total_provisioned_disk=vm['TotalProvisionedSpace']
    total_snap_disk=0
    for disk in vm['disks_info']:
      # if disk.get("provisioned_disk_size"): #VDI有磁盘不存在provisioned_disk属性
      #   total_provisioned_disk+=disk["provisioned_disk_size"]  
      # total_used_disk+=disk["used_disk_size"]
      total_snap_disk+=disk["disk_snap_size"]
    # total_snap_spaceinGB=Decimal(total_snap_spaceinByte/1024/1024/1024).quantize(Decimal('0.0'))
    # print("-----")
    # print("Total Provisioned disk: {}".format(total_provisioned_disk))
    # print("Total used disk: {}".format(total_provisioned_disk))
    # print("Total snapshot disk: {}".format(total_provisioned_disk))


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
  
  return [vms_top10_snapshotSize, \
          vms_top10_Used_diskSize, \
          vms_top10_Provisioned_diskSize, \
          vms_top10_mem,\
          vms_top10_vCPU,\
          vms_guest_os_stastic_list, \
          vms_powerOn_num, \
          vms_powerOff_num,\
          vm_tools_list,\
          tools_outdate, \
          tools_up2date,\
          tools_notInstalled,\
          tools_Unmanaged
          ]


# @app.route('/virtualmachine/<vm_name>')
def show_vm(vm_name:str):
  vms_file=file_search(data_dir,'vms-','.json')
  if len(vms_file)==1:
    with open(vms_file[0],) as f:
      data=json.load(f)
    f.close
  vm_info=[]
  vm_perf_metric=[]
  for vm in data:
    if vm['Display_name']==vm_name:
      vm_info.append(vm)
      vm_perf_metric=vm["vm_perf_metric"]
  return [vm_info,vm_perf_metric]


#数据展现页面
@app.route('/inventory',methods=['GET','POST'])
def datacenter():
  inventory_id=request.args.get('id',default="",type=str)
  vm_name=request.args.get('vm_name',default="",type=str)
  # print(vm_name)
  if inventory_id=="" and vm_name=="":
     para_list=show_vcenter()
     return render_template('vcenter.html', tree=BuildInventoryTree(),\
                        vcsa_fs=para_list[0],vcsa_certs_info=para_list[1],\
                          cert_status_counter=para_list[2],\
                          servicesStatus_list=para_list[3], \
                          root_pass_lines=para_list[4], \
                            alarm_list=para_list[5],\
                              alarm_ack=para_list[6])
  # return [ 
  #         vcsa_info, 
  #         vcsa_certs_info,
  #         cert_status_counter, 
  #         servicesStatus_list, 
  #         root_pass_lines,                        
  #         alarm_list,
  #         alarm_ack ]

  elif len(inventory_id)>0:
     path_list=inventory_id.split('-')
     path_len=len(path_list)
     if path_len==1:
        return redirect('inventory')
     elif path_len==2:
        para_list=show_datacenter(path_list)
        return render_template('datacenter.html',dc_tree=para_list[0],dc_data=para_list[1],dc_network_tree=para_list[2],tree=BuildInventoryTree())
     elif path_len==3:
        cls_data=show_cluster(path_list)
        return render_template('clusters.html',cluster=cls_data,tree=BuildInventoryTree())
     elif path_len==4:
        host_data=show_host(path_list)
        return render_template('host.html',host_data=host_data,tree=BuildInventoryTree())
  
  if vm_name=="all":
      para_list=show_VMSummary()
      return render_template('vms_summary.html',vms_top10_snapshotSize=para_list[0],vms_top10_Used_diskSize=para_list[1], \
                      vms_top10_Provisioned_diskSize=para_list[2], \
                      vms_top10_mem=para_list[3],\
                      vms_top10_vCPU=para_list[4],\
                      vms_guest_os_stastic_list=para_list[5], \
                      vms_powerOn_num=para_list[6], \
                      vms_powerOff_num=para_list[7],\
                      vm_tools_list=para_list[8],\
                      tools_outdate=para_list[9], \
                      tools_up2date=para_list[10],\
                      tools_notInstalled=para_list[11],\
                      tools_Unmanaged=para_list[12],\
                      tree=BuildInventoryTree()
                      )
  else:
     para_list=show_vm(vm_name)
     return render_template('virtualmachine.html',tree=BuildInventoryTree(),vm_info=para_list[0],vm_perf_metric=para_list[1])

@app.route('/hardwareStatus',methods=['GET','POST'])
def hardwareStatus():
   host_id=request.args.get('host_id',default="",type=str)
   
   ipmi_merge_file=os.path.join(data_dir,'hosts_hardware_info.json')
   if not os.path.exists(ipmi_merge_file):
      ipmi_merge_file=ipmi_data_merge()
   data=show_ipmi_data(ipmi_merge_file)

   #host hardware summary data 
   hosts_hardware_summary_data=[]   
   for host in data:
      host_hardware_summary={}
      host_hardware_summary['host']=host['host']
      host_hardware_summary['systemData']={}
      host_hardware_summary['systemData']['Model']=host['systemData']['Model']
      host_hardware_summary['systemData']['Manufacturer']=host['systemData']['Manufacturer']
      host_hardware_summary['systemData']['BiosVersion']=host['systemData']['BiosVersion']
      host_hardware_summary['systemData']['SerialNumber']=host['systemData']['SerialNumber']
      host_hardware_summary['systemData']['ProcessorSummary']={}
      host_hardware_summary['systemData']['ProcessorSummary']['Model']=host['systemData']['ProcessorSummary']['Model']
      host_hardware_summary['systemData']['ProcessorSummary']['Count']=host['systemData']['ProcessorSummary']['Count']
      host_hardware_summary['systemData']['ProcessorSummary']['Status']={}
      host_hardware_summary['systemData']['ProcessorSummary']['Status']['Health']=host['systemData']['ProcessorSummary']['Status']['Health']
      host_hardware_summary['systemData']['MemorySummary']={}
      host_hardware_summary['systemData']['MemorySummary']['TotalSystemMemoryGiB']=host['systemData']['MemorySummary']['TotalSystemMemoryGiB']
      host_hardware_summary['systemData']['MemorySummary']['Status']={}
      host_hardware_summary['systemData']['MemorySummary']['Status']['Health']=host['systemData']['MemorySummary']['Status']['Health']
      host_hardware_summary['systemData']['Status']=host['systemData']['Status']
      hosts_hardware_summary_data.append(host_hardware_summary)   
   
   single_host_detail={}
   if host_id=="":
      host_id=data[0]['host']
   
  

   for host in data:
      if host['host']==host_id:
        single_host_detail=host
   
   
   
   return render_template('ipmi.html',data=hosts_hardware_summary_data,single_host_detail=single_host_detail)

if __name__=='__main__':
    app.run(debug=True,port=9999)
    multiprocessing.freeze_support()