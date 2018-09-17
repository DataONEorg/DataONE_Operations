# This script allows one to alter rightsholder value for sysmeta on a V2 node. The operation is performed
# on both the MN and the CN using python library.  
# Requires an input file named pids.txt in which each pid to be altered is on a new line.
# To be executes on CN due to requiring CN cert access as well as copies of the MN cert.
# Last tested using dataone.libclient version 2.4.2 (python 2.7)

# execute as sudo for access to cn cert: sudo /filepath/my_venv/bin/python update_rightsholder.py

import d1_client.mnclient_2_0
import logging
logging.basicConfig(filename='cleanupRH-errors.log',
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    level=logging.ERROR)
logger = logging.getLogger(__name__)

input = open('pids.txt')

mn_url = "https://mynode.dataone.org/mn"
cn_url = "https://cn.dataone.org/cn"
mn_cert = 'urn_node_NODE.crt'
mn_key = 'urn_node_NODE.key'
cn_auth_cert_combined = '/path/to/CN.pem'


mn_client = d1_client.mnclient_2_0.MemberNodeClient_2_0(
  mn_url, cert_pem_path=mn_cert, cert_key_path=mn_key, timeout=120.0)

cn_client = d1_client.mnclient_2_0.MemberNodeClient_2_0(
  cn_url, cert_pem_path=cn_auth_cert_combined, cert_key_path=cn_auth_cert_combined, timeout=120.0)

def main():

  try:
    pids = input.readlines()
  except Exception:
    print('failure to read file')
  for pid in pids:
    pid = pid.strip()
    print(pid);
    try:
      sysmeta_pyxb = mn_client.getSystemMetadata(pid)
      sysmeta_pyxb.rightsHolder = 'CN=urn:node:NODE,DC=dataone,DC=org'
      mn_client.updateSystemMetadata(pid, sysmeta_pyxb)
      cn_client.updateSystemMetadata(pid, sysmeta_pyxb)
      
    except Exception as e:
      print(e)
      print('\n\n')
      logging.error(e)

if __name__ == "__main__":
  main()
