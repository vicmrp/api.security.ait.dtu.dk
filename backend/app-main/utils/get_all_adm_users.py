from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from dotenv import load_dotenv
import os
from utils import active_directory_connect
from ldap3 import Server, Connection, ALL, SUBTREE

from ldap3 import Server, Connection, ALL, SUBTREE

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Connect to Active Directory
        conn, message = active_directory_connect.active_directory_connect()

        if not conn:
            print('Failed to connect to AD:', message)
            return

        if not conn.bind():
            print('Error in bind', conn.result)
            return

        # # DTU Base Users Search
        # base_dn = "OU=DTUBaseUsers,DC=win,DC=dtu,DC=dk"
        # search_filter = "(objectClass=user)"
        # search_attributes = ["cn"]
        # dtu_base_users = self.perform_search(conn, base_dn, search_filter, search_attributes)
        # print("DTU Base Users:", dtu_base_users)


        # DTU Admin Users
        base_dn = "DC=win,DC=dtu,DC=dk"
        search_filter = "(&(objectClass=user)(SamAccountName=adm-*))"
        search_attributes = ["SamAccountName"]
        adm_users = self.perform_search(conn, base_dn, search_filter, search_attributes)
        print("Admin Users:", adm_users)

        # how do i find vicre in a list of adm_users
        vicre = [user for user in adm_users if user.entry_attributes_as_dict['sAMAccountName'][0] == 'adm-vicre']
        dast = [user for user in adm_users if user.entry_attributes_as_dict['sAMAccountName'][0] == 'dast-vicre']




        # adm_users = []
        # for user in dtu_base_users:
        #     base_dn = "DC=win,DC=dtu,DC=dk"
        #     search_filter = f"(&(objectClass=user)(SamAccountName=adm-{user}))"
        #     search_attributes = ["cn"]
        #     # user name vicre
        #     if user == 'vicre' or user == 'dast':
        #         adm_user = self.perform_search(conn, base_dn, search_filter, search_attributes)
        #         adm_users.extend(adm_user)
        #     adm_user = self.perform_search(conn, base_dn, search_filter, search_attributes)
        #     adm_users.extend(adm_user)

        # print("ADM Users:", adm_users)



        # # Users starting with "adm-" Search
        # base_dn = "DC=win,DC=dtu,DC=dk"  # Adjusted to cover the broader directory
        # search_filter = "(&(objectClass=user)(cn=adm-*))"  # Filter to find users starting with "adm-"
        # adm_users = self.perform_search(conn, base_dn, search_filter, search_attributes)
        # print("Users starting with 'adm-':", adm_users)


        # # All users search
        # base_dn = "DC=win,DC=dtu,DC=dk"
        # search_filter = "(objectClass=user)"  # Filter to find any user
        # search_attributes = ["cn"]
        # all_users = self.perform_search(conn, base_dn, search_filter, search_attributes)
        # # print("All users:", all_users)




        # # Specific users search in all_users list
        # # from all users get all users that starts with 'adm-'
        # # adm_users = [user for user in all_users if user.startswith('adm-')]

        # # see if you cant find the adm_users in dtu_base_users
        # # dtu_base_adm_users = [user for user in adm_users if user.rsplit('-', 1)[-1] in dtu_base_users]
        # # print("DTU Base Users starting with 'adm-':", dtu_base_adm_users)
        # adm_users = [user for user in all_users if user.startswith('adm-')]
        # specific_users = ['vicre', 'adm-vicre', 'dast', 'adm-dast']
        # found_users = [user for user in all_users if user in specific_users]
        # print("Found users:", found_users)

        # #dtu_base_adm_users = ["adm-" + user for user in dtu_base_users if user in adm_users]
        # dtu_base_adm_users = [user for user in adm_users if user.rsplit('-', 1)[-1] in dtu_base_users]
        # print("DTU Base Users starting with 'adm-':", dtu_base_adm_users)

    def perform_search(self, conn, base_dn, search_filter, search_attributes):
        page_size = 500
        paged_cookie = None
        users_list = []

        more_pages = True
        while more_pages:
            conn.search(search_base=base_dn,
                        search_filter=search_filter,
                        search_scope=SUBTREE,
                        attributes=search_attributes,
                        paged_size=page_size,
                        paged_cookie=paged_cookie)

            # Process each entry
            for entry in conn.entries:
                user_name = entry
                users_list.append(user_name)

            # Handle paging if there are more pages
            more_pages = bool(conn.result['controls']['1.2.840.113556.1.4.319']['value']['cookie'])
            if more_pages:
                paged_cookie = conn.result['controls']['1.2.840.113556.1.4.319']['value']['cookie']
            else:
                paged_cookie = None

        return users_list




def run():
    command = Command()
    command.handle(None, None)
    print('done')




# if main 
if __name__ == "__main__":
    run()
