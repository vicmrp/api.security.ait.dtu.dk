from ldap3 import Server, Connection, SUBTREE
import os
from dotenv import load_dotenv

def run():
    # Get username and password from .env file
    load_dotenv()
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    
    user_samaccountname = 'adm-vicre'

    # LDAP settings
    server_uri = "ldaps://win.dtu.dk"
    bind_dn = f"CN={username},OU=AIT,OU=DTUBaseUsers,DC=win,DC=dtu,DC=dk"


    # Connect to the server
    server = Server(server_uri, use_ssl=True)
    conn = Connection(server, bind_dn, password)

    # Bind to the server
    if not conn.bind():
        print('error in bind', conn.result)
        return
    
    # Get the DN of the user
    user_search_filter = f"(sAMAccountName={user_samaccountname})"
    conn.search("DC=win,DC=dtu,DC=dk", user_search_filter, attributes=["distinguishedName"])
    if not conn.entries:
        print("User not found.")
        return
    user_dn = conn.entries[0].distinguishedName.value


    # OUs to check against
    ou1 = 'OU=AIT,OU=ITAdmUsers,OU=Delegations and Security,DC=win,DC=dtu,DC=dk'
    ou2 = 'OU=Institut IT Personnel,OU=ITAdmUsers,OU=Delegations and Security,DC=win,DC=dtu,DC=dk'

    def is_user_in_ou(user_dn, ou_path):
        return ou_path in user_dn

    # Check if user DN is under the given OUs
    if is_user_in_ou(user_dn, ou1) or is_user_in_ou(user_dn, ou2):
        print(f"{user_dn} is admin!")
    else:
        print(f"{user_dn} is NOT admin!")



if __name__ == '__main__':
    run()


