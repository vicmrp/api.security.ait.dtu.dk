from .active_directory_connect import active_directory_connect
from ldap3.core.exceptions import LDAPKeyError
from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, ALL
from datetime import datetime, timedelta, timezone

# returns computer that has nat been logged in witing x days
# write a good function name 

def get_inactive_computers(days=30, base_dn='DC=win,DC=dtu,DC=dk'):

    # Connect to Active Directory
    conn, message = active_directory_connect.active_directory_connect()

    # DTU-CND1363SBJ
    # get this computers info

    # Bind to the server
    if not conn.bind():
        print('error in bind', conn.result)
    else:
        # Define search parameters
        # base_dn = "DC=win,DC=dtu,DC=dk"
        search_filter = "(objectClass=computer)"
        search_attributes = ["lastLogonTimestamp", "userAccountControl", 'objectCategory', 'cn']
        # search_attributes = ALL_ATTRIBUTES
        page_size = 500

        # Create a Paged Cookie to keep track of the paging
        paged_cookie = None



        
        utc_timezone = timezone.utc

        check_time = datetime.now(utc_timezone) - timedelta(days=days)
        # add timezone to check_time

        
        active_directory_objects = []
        while True:
            # Perform the search with the current page cookie
            conn.search(base_dn, search_filter, SUBTREE, attributes=search_attributes, paged_size=page_size, paged_cookie=paged_cookie)
            # Print the results
            
            for entry in conn.entries:
                try:

                    # chack if entry.entry_dn (string) contains lower("disaled")
                    # if it does, then skip this entry
                    # if not, then continue
                    if "disabled" in entry.entry_dn.lower():
                        continue


                    # Check if 'lastLogonTimestamp' attribute exists
                    if not hasattr(entry, 'lastLogonTimestamp') or entry.lastLogonTimestamp is None:
                        continue
                    

                    if entry.lastLogonTimestamp.value is None:
                        continue
                    
                    account_is_disabled = entry.userAccountControl.value & 2 != 0

                    
                    if account_is_disabled == True:
                        continue


                    if entry.lastLogonTimestamp.value < check_time:
                        active_directory_objects.append({
                            "lastLogonTimestamp": entry.lastLogonTimestamp.value,
                            "computer_name": entry.cn.value,
                            "entry_dn": entry.objectCategory.value
                        })
                except LDAPKeyError:
                    print("Error with entry:", entry)



            # Check if more pages are available
            paged_cookie = conn.result['controls']['1.2.840.113556.1.4.319']['value']['cookie']
            if not paged_cookie:
                break

        # Unbind and close the connection
        conn.unbind()


    # check if 

    # # Create an object that looks like this: 
    # # {
    #     Days: days,
    #     Number_of_computers = len(active_directory_objects)
    #     Computers: [
    #         {
    #             "lastLogonTimestamp": entry.lastLogonTimestamp.value,
    #             "computer_name": entry.cn.value,
    #             "entry_dn": entry.objectCategory.value
    #         }
    #     ]


    # return active_directory_objects
        

    # Prepare the final object to return
    result = {
        "inactive_days": days,
        "number_of_computers": len(active_directory_objects),
        "inactive_computers": active_directory_objects
    }

    return result


def run():
    inactive_computers = get_inactive_computers(days=30, base_dn='DC=win,DC=dtu,DC=dk')
    print(inactive_computers)




# if main 
if __name__ == "__main__":
    run()
