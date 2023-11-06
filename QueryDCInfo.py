from pyVmomi import vim
import os 
import json
import datetime
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
        logger.error(f"Failed to connect to vCenter at {vchost}: {e}")
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


# Method that populates objects of type vimtype
def get_all_objs(content, vimtype):
    obj = []
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for managed_object_ref in container.view:
        # obj.update({managed_object_ref: managed_object_ref.name})
        obj.append(managed_object_ref)
    return obj

def QueryDCsInfo(si):
    content=si.content
    print("Gathering vSphere Datacenters information")
    logger.info("开始收集Datacenter信息!")
    dcs=get_all_objs(content,[vim.Datacenter])
    datacenters=[]
    for dc in dcs:
        logger.info("开始收集Datacenter："+ dc.name+" 信息")
        dc_config={}
        sub_clusters=[]
        
        
        vdss=[]
        for ces in dc.networkFolder.childEntity:
            if isinstance(ces,vim.DistributedVirtualSwitch):
                # print(ces.name)  # dvs name
                vds={}
                vds['name']=ces.name
                portgroups=[]
                for pg in  ces.portgroup:
                    portgroup={}     # Portgroups that are defined on the switch.[]
                    # print(pg.name)
                    # print(pg.key) 
                    # print(pg.config)
                    portgroup['name']=pg.name
                    portgroup['key']=pg.key
                    vlanId=pg.config.defaultPortConfig.vlan.vlanId
                    if isinstance(vlanId,list):
                        if vlanId[0].start==0 and vlanId[0].end==4094:
                            vlanId=4095
                    portgroup['vlan']=vlanId

                    # print(vlanId)
                    portgroup['uplinkTeamingPolicy']={"value":pg.config.defaultPortConfig.uplinkTeamingPolicy.policy.value,"inherited":pg.config.defaultPortConfig.uplinkTeamingPolicy.policy.inherited}
                    portgroup['uplinkPortOrder']={"activeUplinkPort":pg.config.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.activeUplinkPort, \
                                                  "standbyUplinkPort":pg.config.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.standbyUplinkPort, \
                                                    "inherited":pg.config.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.inherited}

                    portgroup['uplink']=pg.config.uplink
                    portgroups.append(portgroup)
                vds['portgroups']=portgroups
                
                # for hostmember in ces.config.host:
                #     print(ces.name+"--"+hostmember.config.host.name)
                connectedHosts=[]
                for host in ces.config.host:
                    connectedHosts.append(host.config.host.name)
                vds['connectedHosts']=connectedHosts
                vdss.append(vds)
        for ces in dc.hostFolder.childEntity:
            if isinstance(ces,vim.ClusterComputeResource):
                cluster={}
                hosts=[]
                cluster['name']=ces.name
                cluster['type']='cluster'
                for sub_host in ces.host:
                    host={}
                    host['name']=sub_host.name
                    host['type']='host'
                    host['children']=[]
                    hosts.append(host)
                cluster['children']=hosts
            sub_clusters.append(cluster)

        dc_config['name']=dc.name
        dc_config['type']='datacenter'
        
        dc_config['children']=sub_clusters
        dc_config['dvs']=vdss
        datacenters.append(dc_config)
        
    # return datacenters

    
    print("write retrieved information abouts vsphere datacenter(s) in to json file {}".format(dc_json_file))
    with open(dc_json_file,'w') as f:
        json.dump(datacenters,f,indent=4,ensure_ascii=False,default=str,cls=MyEncoder)
        logger.info("DC信息写入文件："+dc_json_file)
    f.close  
    print("All datacenter(s) information are saved!")
    logger.info("the information acquisition of datacenter(s) is finished!")

if __name__=="__main__":
    # Check if the command-line arguments are provided
    if len(sys.argv) != 4:
        print("Usage: "+ os.path.basename(__file__)+" <vchost> <vcuser> <vcpassword>")
        sys.exit(1)

    # Retrieve the arguments
    vchost = sys.argv[1]
    vcuser = sys.argv[2]
    vcpassword = sys.argv[3]

    print(sys.argv)

    s = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    s.verify_mode = ssl.CERT_NONE

    cwd = os.getcwd()
    current_time=datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    dc_json_file=os.path.join(cwd,'data',"dc-"+current_time+".json")

    logfile_path=os.path.join(cwd,'data','log',"dcInfo_gathering.log")
    log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
    logger=logging.getLogger('DC_logger')
    fh=logging.FileHandler(filename=logfile_path,mode='a')
    fh.setLevel(logging.INFO)
    fh.setFormatter(log_formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)

    si=establish_connection(vchost=vchost,vcuser=vcuser,vcpassword=vcpassword)
    QueryDCsInfo(si)