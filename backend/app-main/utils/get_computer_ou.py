# utils.py
from ldap3 import Server, Connection, ALL
# load dotent
from dotenv import load_dotenv
import os

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)




def get_computer_ou(computer_name, ad_server, ad_username, ad_password):



    # server = Server(ad_server, get_info=ALL)
    server = Server(ad_server, use_ssl=True, get_info=ALL)
    bind_dn = f"CN={ad_username},OU=AIT,OU=DTUBaseUsers,DC=win,DC=dtu,DC=dk"
    # conn = Connection(server, bind_dn, ad_password, auto_bind=True)
    # conn = Connection(server, user=ad_username, password=ad_password, auto_bind=True)
    conn = Connection(server, bind_dn, ad_password, auto_bind=True)
    
    search_filter = f"(&(objectClass=computer)(name={computer_name}))"
    # conn.search('dc=yourdomain,dc=com', search_filter, attributes=['distinguishedName'])
    conn.search('DC=win,DC=dtu,DC=dk', search_filter, attributes=['distinguishedName'])
    
    if conn.entries:
        dn = conn.entries[0]['distinguishedName'].value
        # Extract OU from the DN, you might need additional parsing based on your AD structure.
        ou = ','.join(dn.split(',')[1:])
        return ou

    return None
