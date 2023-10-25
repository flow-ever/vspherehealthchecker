import ssl
from pyVim.connect import SmartConnect, Disconnect
import atexit
import time
from datetime import datetime
import multiprocessing
import sys

from QueryVMInfo import QueryVMsInfo
from QueryHostInfo import QueryHostsInfo
from QueryClusterInfo import QueryClustersInfo
from QueryDCInfo import QueryDCsInfo


s = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
s.verify_mode = ssl.CERT_NONE

# Check if the command-line arguments are provided
if len(sys.argv) != 4:
    print("Usage: "+ __name__+" <vchost> <vcuser> <vcpassword>")
    sys.exit(1)

# Retrieve the arguments
vchost = sys.argv[1]
vcuser = sys.argv[2]
vcpassword = sys.argv[3]


def establish_connection(vchost,vcuser,vcpassword):
    try:
        si = SmartConnect(host=vchost, user=vcuser, pwd=vcpassword, sslContext=s)
        atexit.register(Disconnect, si)
        return si
    except Exception as e:
        print(f"Failed to connect to vCenter at {vchost}: {e}")
        return None

def query_vm_info(vchost,vcuser,vcpassword):
    si = establish_connection(vchost,vcuser,vcpassword)
    if si:
        QueryVMsInfo(si)

def query_host_info(vchost,vcuser,vcpassword):
    si = establish_connection(vchost,vcuser,vcpassword)
    if si:
        QueryHostsInfo(si)

def query_cluster_info(vchost,vcuser,vcpassword):
    si = establish_connection(vchost,vcuser,vcpassword)
    if si:
        QueryClustersInfo(s,si, vchost)

def query_dc_info(vchost,vcuser,vcpassword):
    si = establish_connection(vchost,vcuser,vcpassword)
    if si:
        QueryDCsInfo(si)


def Query_vsphere_info(vchost,vcuser,vcpassword):
    processes = []
    time1=time.time()
    
    process01 = multiprocessing.Process(target=query_vm_info(vchost,vcuser,vcpassword))
    process01.start()
    processes.append(process01)

    process02 = multiprocessing.Process(target=query_host_info(vchost,vcuser,vcpassword))
    process02.start()
    processes.append(process02)

    process03 = multiprocessing.Process(target=query_cluster_info(vchost,vcuser,vcpassword))
    process03.start()
    processes.append(process03)

    process04 = multiprocessing.Process(target=query_dc_info(vchost,vcuser,vcpassword))
    process04.start()
    processes.append(process04)

    for process in processes:
        process.join()

    time2 = time.time()
    time_comsuption=time2-time1
    print("Information gathering Job is finished! Time consumed: {} s".format(time_comsuption))
    return time_comsuption

# if __name__=='__main__':
#     vchost = "vcsa.flow-ever.com"
#     vcuser = "administrator@vsphere.local"
#     vcpassword = "123Qwe,."
#     Query_vsphere_info(vchost,vcuser,vcpassword)