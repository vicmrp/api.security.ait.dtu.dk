from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, ALL
from ldap3.core.exceptions import LDAPKeyError
import os
from dotenv import load_dotenv




def run():

    # Get username and password from .env file
    load_dotenv()
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")


    # LDAP settings
    server_uri = "ldaps://win.dtu.dk"
    bind_dn = f"CN={username},OU=AIT,OU=DTUBaseUsers,DC=win,DC=dtu,DC=dk"

    # Connect to the server
    server = Server(server_uri, use_ssl=True, get_info=ALL)
    conn = Connection(server, bind_dn, password)

    # Bind to the server
    if not conn.bind():
        print('error in bind', conn.result)
    else:
        # Define search parameters
        # base_dn = "OU=STUDENTS,OU=DTUBaseUsers,DC=win,DC=dtu,DC=dk"
        base_dn = "DC=win,DC=dtu,DC=dk"
        search_filter = "(objectClass=user)"
        search_attributes = ["Name", "givenName", "sn", "mail"]
        page_size = 500

        # Create a Paged Cookie to keep track of the paging
        paged_cookie = None

    search_filter = '(objectClass=organizationalUnit)'
    conn.search(base_dn, search_filter, SUBTREE, attributes=['ou'])

    for entry in conn.entries:
        print(entry.ou)


# if main 
if __name__ == "__main__":
    run()
