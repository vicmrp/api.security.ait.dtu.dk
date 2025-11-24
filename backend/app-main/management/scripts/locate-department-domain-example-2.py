from ldap3 import Server, Connection, SUBTREE
import os
from dotenv import load_dotenv

def run():
    # Get username and password from .env file
    load_dotenv()
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    
    user_samaccountname = 'dast'

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
    if not conn.search("DC=win,DC=dtu,DC=dk", user_search_filter, attributes=["distinguishedName"]):
        print("User not found.")
    else:
        user_dn = conn.entries[0].distinguishedName.value
        print(f"Found user DN: {user_dn}")

        # Now, let's find the admin account for the user
        admin_search_filter = f"(sAMAccountName=adm-*{user_samaccountname}*)"
        search_ous = [
            "OU=AIT,OU=ITAdmUsers,OU=Delegations and Security,DC=win,DC=dtu,DC=dk",
            "OU=Institut IT Personnel,OU=ITAdmUsers,OU=Delegations and Security,DC=win,DC=dtu,DC=dk"
        ]
        admin_found = False

    for ou in search_ous:
        if conn.search(ou, admin_search_filter, attributes=["distinguishedName"]):
            admin_dn = conn.entries[0].distinguishedName.value
            print(f"Found admin account in {ou}: {admin_dn}")
            admin_found = True
            break
        else:
            print("Admin account not found.")

    if not admin_found:
        print("Admin account not found.")
        return
    
    # Get the Company value
    user_search_filter = f"(distinguishedName={user_dn})"
    conn.search("DC=win,DC=dtu,DC=dk", user_search_filter, attributes=["company"])
    if not conn.entries:
        print("User not found.")
        return
    company = conn.entries[0].company.value

    print(f"Company: {company}")

    # If the Company value is AIT, then search and validate existence of OU=AIT,DC=win,DC=dtu,DC=dk
    if company == 'AIT':
        ou_search_filter = "(ou=AIT)"
        conn.search("DC=win,DC=dtu,DC=dk", ou_search_filter, search_scope=SUBTREE)

        # If the search returns an entry, it means the OU exists
        if conn.entries:
            print("OU=AIT,DC=win,DC=dtu,DC=dk exists.")
        else:
            print("OU=AIT,DC=win,DC=dtu,DC=dk does not exist.")
    
    else:
        # Search for the existence of OU under OU={company},OU=Institutter,DC=win,DC=dtu,DC=dk
        base_dn = f"OU={company},OU=Institutter,DC=win,DC=dtu,DC=dk"
        ou_search_filter = f"(ou={company})"
        conn.search(base_dn, ou_search_filter, search_scope=SUBTREE)

        # If the search returns an entry, it means the OU exists
        if conn.entries:
            print(f"OU={company},OU=Institutter,DC=win,DC=dtu,DC=dk exists.")
        else:
            print(f"OU={company},OU=Institutter,DC=win,DC=dtu,DC=dk does not exist.")
    
    
    # Else if located the distinguishedName dast.Company value is SUS then search for OU=SUS,OU=Institutter,DC=win,DC=dtu,DC=dk






if __name__ == '__main__':
    run()


