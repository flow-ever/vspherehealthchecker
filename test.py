import argparse
import getpass
import json
import logging
import requests
import sys
import time
import warnings


logging.basicConfig(format='%(message)s', stream=sys.stdout, level=logging.INFO)

def get_redfish_version(idrac_ip,idrac_username,idrac_password):
    global session_uri
    response = requests.get('https://%s/redfish/v1' % idrac_ip,verify=False, auth=(idrac_username, idrac_password))
    data = response.json()
    if response.status_code == 401:
            logging.warning("\n- WARNING, status code %s returned. Incorrect iDRAC username/password or invalid privilege detected." % response.status_code)
            sys.exit(0)
    elif response.status_code != 200:
        logging.warning("\n- WARNING, GET request failed to get Redfish version, status code %s returned" % response.status_code)
        sys.exit(0)
    redfish_version = int(data["RedfishVersion"].replace(".",""))
    if redfish_version >= 160:
        session_uri = "redfish/v1/SessionService/Sessions"
    elif redfish_version < 160:
        session_uri = "redfish/v1/Sessions"
    else:
        logging.error("- ERROR, unable to select URI based off Redfish version")
        sys.exit(0)


def create_x_auth_session(idrac_ip,idrac_username,idrac_password):
    url = 'https://%s/%s' % (idrac_ip, session_uri)
    payload = {"UserName":idrac_username,"Password":idrac_password}
    headers = {'content-type': 'application/json'}
    response = requests.post(url, data=json.dumps(payload), headers=headers, verify=False)
    data = response.json()
    if response.status_code == 201:
        logging.info("\n- PASS, successfully created X auth session")
    else:
        try:
            logging.error("\n- FAIL, unable to create X-auth_token session, status code %s returned, detailed error results:\n %s" % (response.status_code, data))
        except:
            logging.error("\n- FAIL, unable to create X-auth_token session, status code %s returned" % (response.status_code))
        sys.exit(0)
    logging.info("\n- INFO, created session details -\n")
    # for i in response.headers.items():
    #     print("%s: %s" % (i[0],i[1]))
    return response.headers.get("x-auth-token")

def delete_x_auth_session(idrac_ip,idrac_username,idrac_password):
    url = 'https://%s/%s/%s' % (idrac_ip, session_uri, "delete")
    try:
        headers = {'content-type': 'application/json'}
        response = requests.delete(url, headers=headers, verify=False,auth=(idrac_username,idrac_password))
    except requests.ConnectionError as error_message:
        logging.error("- FAIL, requests command failed to GET job status, detailed error information: \n%s" % error_message)
        sys.exit(0)
    if response.status_code == 200:
        logging.info("\n- PASS, successfully deleted iDRAC session ID %s" % "delete")
    else:
        data = response.json()
        logging.info("\n- FAIL, unable to delete iDRAC session, status code %s returned, detailed error results:\n %s" % (response.status_code, data))
        sys.exit(0)

idrac_ip,idrac_username,idrac_password='192.168.10.230','root','calvin'

get_redfish_version(idrac_ip,idrac_username,idrac_password)
token=create_x_auth_session(idrac_ip,idrac_username,idrac_password)
print('token:'+token)

response = requests.get('https://%s/redfish/v1/Systems/System.Embedded.1/NetworkInterfaces/NIC.Embedded.1' % idrac_ip, verify=False, headers={'X-Auth-Token': token}) 
print(response.json())

# # 'https://'+host+'/redfish/v1/Systems/System.Embedded.1/Storage'
# response = requests.get('https://%s/redfish/v1/Systems/System.Embedded.1/Storage' % idrac_ip, verify=False, headers={'X-Auth-Token': token}) 
# print(response)

# delete_x_auth_session(idrac_ip,idrac_username,idrac_password)


