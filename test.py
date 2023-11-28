from pyVmomi import vim
import os 
import json
import datetime
import logging
from pyVim.connect import Disconnect,SmartConnectNoSSL
import atexit
import sys
import vsanmgmtObjects
import vsanapiutils
from packaging.version import Version
from decimal import Decimal
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import pytz


class BColors(object):
    """A class used to represent ANSI escape sequences
       for console color output.
    """
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    reset = "\033[0m"
    bold = "\033[1m"
    white = "\033[38;2;255;255;255m"
    black = "\033[38;2;0;0;0m"
    red = "\033[38;2;255;0;0m"
    green = "\033[38;2;0;255;0m"
    blue = "\033[38;2;0;0;255m"
    white_bg = "\033[48;2;255;255;255m"
    black_bg = "\033[48;2;0;0;0m"
    red_bg = "\033[48;2;255;0;0m"
    green_bg = "\033[48;2;0;255;0m"
    blue_bg = "\033[48;2;0;0;255m"

def establish_connection(vchost,vcuser,vcpassword):
    try:
        si = SmartConnectNoSSL(host=vchost, user=vcuser, pwd=vcpassword)
        atexit.register(Disconnect, si)
        return si
    except Exception as e:
        print(f"Failed to connect to vCenter at {vchost}: {e}")
        return None


def get_all_objs(content, vimtype):
    obj = []
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for managed_object_ref in container.view:
        # obj.update({managed_object_ref: managed_object_ref.name})
        obj.append(managed_object_ref)
    container.Destroy()
    return obj

vcuser='administrator@vsphere.local'
# vchost='192.168.10.82'
# vcpassword='123Qwe,.'
vchost='192.168.83.212'
vcpassword='eRB$i5PUl@20211101'

si=establish_connection(vchost,vcuser,vcpassword)
content=si.content
dcs=get_all_objs(content,[vim.Datacenter])
for dc in dcs:
    #list network type objects
    vdss=[]
    for netobj in dc.networkFolder.childEntity:
        if isinstance(netobj,vim.DistributedVirtualSwitch):
            vds={}
            vds['name']=netobj.name
            
            vds['portgroups']=[]
            #get portgroup information
            for ptgrp in netobj.portgroup:
                if ptgrp.config.name=='PG_VM' or ptgrp.config.name=='PG_Trunk' :
                    pass
                pg={}
                pg['name']=ptgrp.config.name
                pg['uplink']=ptgrp.config.uplink
                if hasattr(ptgrp,'backingType'):
                    pg['backingType']=ptgrp.config.backingType  #since vsphere vpi 7.0
                else:
                    pg['backingType']=None
                vlaninfo=ptgrp.defaultPortConfig.vlan
                if isinstance(vlaninfo,'vim.dvs.VmwareDistributedVirtualSwitch.TrunkVlanSpec'):  #端口组为trunk类型
                    vlanlist=[]
                    for item in vlaninfo.vlanId:
                        if item.start==item.end:
                            vlanlist.append(str(item.start))
                        else:
                            vlanlist.append(str(item.start)+'-'+str(item.end))
                    pg['vlan_id']=','.join(vlanlist)
                else:
                    pg['vlan_id']=str(vlaninfo.vlanId)
                uplinkpolicy=ptgrp.defaultPortConfig.uplinkTeamingPolicy
                uplinkportorder=uplinkpolicy.uplinkPortOrder
                activeUplinkPort=uplinkportorder.activeUplinkPort #[]
                standbyUplinkPort=uplinkportorder.standbyUplinkPort #[]
                pg['activeUplinkPort']=activeUplinkPort
                pg['standbyUplinkPort']=standbyUplinkPort
                vds['portgroups'].append(pg)
            #get hosts that connected to the vds
            connectedHosts=[]
            for host in netobj.config.host:
                connectedHosts.append(host.config.host.name)
            vds['connectedHosts']=connectedHosts
            
            vdss.append(vds)

    datastores=[]
    for ds in dc.datastoreFolder.childEntity:
        ds_info={}
        ds_info['name']=ds.name
        ds_info['hosts']=ds.host #Hosts attached to this datastore.
        ds_info['vm']=ds.vm
        ds_info['maxVirtualDiskCapacity']=ds.info.maxVirtualDiskCapacity #The maximum capacity of a virtual disk which can be created on this volume.
        ds_info['capacity']=ds.summary.capacity  #Maximum capacity of this datastore, in bytes. 
        ds_info['freeSpace']=ds.summary.freeSpace #Free space of this datastore, in bytes.
        ds_info['multipleHostAccess']=ds.summary.multipleHostAccess
        ds_info['fstype']=ds.summary.type
        ds_info['type']='datastore'
        ds_info['uncommited']=ds.summary.uncommitted if ds.summary.uncommitted else 0 #Total additional storage space, in bytes, potentially used by all virtual machines on this datastore. 
        ds_info['over_provision']=ds.summary.capacity-ds.summary.freeSpace+ds.summary.uncommitted

                


            

    # #list datastore type objects
    # for dsobj in dc.datastore:
    #     if dsobj.type=="VmwareDistributedVirtualSwitch":
    #         print(dsobj.name)        