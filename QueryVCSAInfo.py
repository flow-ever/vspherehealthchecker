import paramiko
import os
import datetime
import socket
import sys
import time
import logging
import mysql.connector
from mysql.connector import errorcode



# paramiko.util.log_to_file( 'ssh.log' )

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

def connectdb(db_host,db_user,db_passwd,db_name):
    try:
        mydb = mysql.connector.connect(host=db_host,user=db_user,password=db_passwd,database=db_name)
        logger.info('Succesfully connect DB HOST:'+db_host)
        return mydb
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Invalid username or password")
            logger.error("Invalid username or password to connect to "+db_host)
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database "+ db_name +" does not exist")
            logger.error("Database "+ db_name +" does not exist")
        elif err.errno == errorcode.CR_SERVER_GONE_ERROR:
            print("Server "+ db_host +" is unavailable")
            logger.error("Server "+ db_host +" is unavailable")
        else:
            print("Unknown connection error:", err)
            logger.error("Unknown connection error:", err)
        return err.errno

# print("write retrieved information abouts vcenter Server in to json file {}".format(vcsa_json_file))

def QueryVCSAInfo(vchost,rootPassword):
    
    logger.info("开始收集VCSA虚拟机内部信息")
    cmd_enable_shell='shell.set --enabled true\n'
    cmd_entershell='shell'
    cmd_mem='free -h'
    cmd_df='df -h'
    cmd_cert_check='for store in $(/usr/lib/vmware-vmafd/bin/vecs-cli store list | grep -v TRUSTED_ROOT_CRLS); \
                do echo "[*] Store :" $store; /usr/lib/vmware-vmafd/bin/vecs-cli entry list --store $store --text \
                | grep -ie "Alias" -ie "Not After";done;'
    cmd_vcservice_list='service-control --list-services'
    cmd_vcservice_check='for i in $(/usr/lib/vmware-vmon/vmon-cli -l);do /usr/lib/vmware-vmon/vmon-cli -s $i;done'
    cmd_passwdExpire_check='chage -l root'
    commands=[cmd_enable_shell,cmd_entershell,cmd_mem,cmd_df,cmd_cert_check,cmd_vcservice_list,cmd_vcservice_check,cmd_passwdExpire_check]
    
    try:
        # Create an SSH client object
        client = paramiko.SSHClient()

        # Automatically add the server's host key (for development/testing; improve security for production)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        logger.info("Connecting to VCSA...")
        print("Connecting to VCSA...")

        # Connect to the VCSA SSH server
        client.connect(vchost, port=22, username='root', password=rootPassword, timeout=5)
        channel = client.invoke_shell()
        
        data = ''
        for cmd in commands:
            channel.send(cmd + '\n')
            logger.info('Executing command:' + cmd)
            time.sleep(2)

            while not  channel.recv_ready():
                time.sleep(1)

            data += channel.recv(20480).decode('ascii').strip('\n')
    

        logger.info('收集的信息写入文件：'+vcsa_json_file)
        with open(vcsa_json_file,'a') as f:
            f.writelines(data)
        f.close()
              

    except paramiko.AuthenticationException as e:
        print(f"SSH authentication error: {e}")
        logger.info(f"SSH authentication error: {e}")
    except paramiko.SSHException as e:
        print(f"SSH error: {e}")
        logger.info(f"SSH error: {e}")
    except socket.error as e:
        print(f"Socket error: {e}")
        logger.info(f"Socket error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        logger.info(f"An unexpected error occurred: {e}")

    finally:
        # Close the SSH connection
        logger.info("the information acquisition of vcsa is finished!")  
        client.close()



if __name__=='__main__':
    # Check if the command-line arguments are provided
    if len(sys.argv) != 3:
        print("Usage: "+ os.path.basename(__file__)+" <vchost> <rootPassword>")
        sys.exit(1)

    # Retrieve the arguments
    vchost = sys.argv[1]
    rootPassword = sys.argv[2]


    QueryVCSAInfo(vchost,rootPassword)




