import paramiko
import os
import datetime
import socket
import sys
import time
import logging




paramiko.util.log_to_file( 'ssh.log' )

# cmds=[]



# print("write retrieved information abouts vcenter Server in to json file {}".format(vcsa_json_file))

def QueryVCSAInfo(vchost,rootPassword):
    logger.info("开始收集VCSA虚拟机内部信息")
    cmd_mem='free -h'
    cmd_df='df -h'
    cmd_cert_check='for store in $(/usr/lib/vmware-vmafd/bin/vecs-cli store list | grep -v TRUSTED_ROOT_CRLS); \
                do echo "[*] Store :" $store; /usr/lib/vmware-vmafd/bin/vecs-cli entry list --store $store --text \
                | grep -ie "Alias" -ie "Not After";done;'
    try:
        # Create an SSH client object
        client = paramiko.SSHClient()

        # Automatically add the server's host key (for development/testing; improve security for production)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print("Connecting to VCSA...")

        # Connect to the VCSA SSH server
        client.connect(vchost, port=22, username='root', password=rootPassword, timeout=5)
        channel = client.invoke_shell()
        out=channel.recv(1024)

        channel.send('shell.set --enabled true\n')
        while not channel.recv_ready():
            time.sleep(2)

        out=channel.recv(1024)
        # print(out.decode("ascii"))

        channel.send('shell\n')
        while not channel.recv_ready():
            time.sleep(3)

        out=channel.recv(1024)
        # print(out.decode("ascii"))

        channel.send(cmd_mem+'\n')
        while not channel.recv_ready():
            time.sleep(3)

        out=channel.recv(2048)
        
        # print(out.decode("ascii"))
        mem_info=out.decode("utf-8")
        with open(vcsa_json_file,'a') as f:
            f.writelines(mem_info)
        f.close()

        channel.send(cmd_df+'\n')
        while not channel.recv_ready():
            time.sleep(3)

        out=channel.recv(2048)
        
        # print(out.decode("ascii"))
        logger.info("收集文件系统使用信息")
        fs_map_info=out.decode("utf-8")
        with open(vcsa_json_file,'a') as f:
            f.writelines(fs_map_info)
        f.close()



        channel.send(cmd_cert_check+'\n')
        while not channel.recv_ready():
            time.sleep(3)

        out=channel.recv(2048)
        # print(out.decode("ascii"))
        cert_info=out.decode("utf-8")
        logger.info("收集证书信息")
        with open(vcsa_json_file,'a') as f:
            f.writelines(cert_info)
        f.close()

        client.close()
        logger.info("the information acquisition of vcsa is finished!")


    except paramiko.ssh_exception.AuthenticationException as e:
        print(f"SSH error: {e}")
        sys.exit(1)
    except paramiko.ssh_exception.SSHException as e:
        print(f"SSH error: {e}")
        sys.exit(1)
    except socket.error:
        print("socket.error")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the SSH connection
        client.close()



if __name__=='__main__':
    # Check if the command-line arguments are provided
    if len(sys.argv) != 3:
        print("Usage: "+ os.path.basename(__file__)+" <vchost> <rootPassword>")
        sys.exit(1)

    # Retrieve the arguments
    vchost = sys.argv[1]
    rootPassword = sys.argv[2]

    cwd = os.getcwd()
    current_time=datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    vcsa_json_file=os.path.join(cwd,'data',"vcsa-"+current_time+".log")   
    logfile_path=os.path.join(cwd,'data','log',"vcsaInfo_gathering.log")

    log_formatter=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s','%Y%m%d %H:%M:%S')
    logger=logging.getLogger('vcsa_logger')
    fh=logging.FileHandler(filename=logfile_path,mode='a')
    fh.setLevel(logging.INFO)
    fh.setFormatter(log_formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)

    QueryVCSAInfo(vchost,rootPassword)



