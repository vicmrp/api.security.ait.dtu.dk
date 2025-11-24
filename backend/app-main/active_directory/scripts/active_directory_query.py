
import datetime
import logging
import os

from ldap3 import SUBTREE, ALL_ATTRIBUTES
from .active_directory_connect import active_directory_connect
from ldap3.core.exceptions import LDAPException

logger = logging.getLogger(__name__)

try:
    _SEARCH_TIME_LIMIT = float(os.getenv('ACTIVE_DIRECTORY_SEARCH_TIMEOUT', '15'))
except (TypeError, ValueError):
    _SEARCH_TIME_LIMIT = 15.0

SEARCH_TIME_LIMIT = max(1, int(_SEARCH_TIME_LIMIT))

def serialize_value(value):
    """
    Convert LDAP attribute values to JSON serializable formats.
    """
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    elif isinstance(value, bytes):
        return value.decode('utf-8', errors='ignore')  # Assuming UTF-8 encoding; adjust as needed.
    else:
        return value

def active_directory_query(*, base_dn, search_filter, search_attributes=ALL_ATTRIBUTES, limit=None, excluded_attributes=[]):
    try:
        conn, message = active_directory_connect()

        # cnvert limit to int
        if limit is not None:
            try:
                limit = int(limit)
            except ValueError:
                print('Invalid limit value. Limit must be an integer.')
                return []

        if not conn:
            print('Failed to connect to AD:', message)
            return []

        if not conn.bind():
            print('Error in bind', conn.result)
            return []

        ldap_list = []
        page_size = 500 if limit is None or limit > 500 else limit
        paged_cookie = None
        entries_collected = 0

        attributes_to_fetch = ALL_ATTRIBUTES if search_attributes is ALL_ATTRIBUTES else search_attributes



        search_timed_out = False

        while True:
            conn.search(
                search_base=base_dn,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes_to_fetch,
                paged_size=page_size,
                paged_cookie=paged_cookie,
                time_limit=SEARCH_TIME_LIMIT,
            )

            for entry in conn.entries:
                if limit is not None and entries_collected >= limit:
                    break

                attr_dict = {}
                for attr in entry.entry_attributes_as_dict.keys():
                    if attr in excluded_attributes:
                        continue  # Skip excluded attributes
                    attr_values = entry.entry_attributes_as_dict.get(attr, [])
                    # serialized_values = [serialize_value(value) for value in attr_values]
                    # attr_dict[attr] = serialized_values
                    attr_dict[attr] = attr_values

                # If search_attributes is not set to ALL_ATTRIBUTES, process only the attributes in search_attributes
                else:
                    attributes_to_process = search_attributes
                for attr in attributes_to_process:
                    attr_values = entry.entry_attributes_as_dict.get(attr, [])
                    # Serialize each attribute value
                    # serialized_values = [serialize_value(value) for value in attr_values]
                    attr_dict[attr] = attr_values

                ldap_list.append(attr_dict)
                entries_collected += 1

            if limit is not None and entries_collected >= limit:
                break

            result_controls = conn.result.get('controls') if isinstance(conn.result, dict) else None
            if result_controls and '1.2.840.113556.1.4.319' in result_controls:
                paged_cookie = result_controls['1.2.840.113556.1.4.319']['value']['cookie']
                if not paged_cookie:
                    break
            else:
                if isinstance(conn.result, dict):
                    description = conn.result.get('description')
                    if description == 'timeLimitExceeded':
                        search_timed_out = True
                        break
                    if description and description != 'success':
                        logger.warning(
                            'Active Directory query returned description=%s for base_dn=%s filter=%s',
                            description,
                            base_dn,
                            search_filter,
                        )
                else:
                    print('Paged search control not found in server response.')
                break

        conn.unbind()
        if search_timed_out:
            logger.warning(
                'Active Directory query time limit (%ss) exceeded for base_dn=%s filter=%s',
                SEARCH_TIME_LIMIT,
                base_dn,
                search_filter,
            )
        return ldap_list


    except LDAPException as error:
        print(f"An error occurred during the LDAP operation: {error}")
        return []
    except Exception as error:
        print(f"An unexpected error occurred: {error}")
        return []




def run():
    
    base_dn = "DC=win,DC=dtu,DC=dk"
    search_filter = "(objectClass=user)"
    limit = 100  # Limit to first 100 users
    users_first_100 = active_directory_query(base_dn=base_dn, search_filter=search_filter, limit=limit)
    print(len(users_first_100))
    print(users_first_100[0]['distinguishedName']) # ['CN=Exchange Online-ApplicationAccount,OU=Users,OU=MailogKalender,OU=BIT-DSG,OU=AIT,DC=win,DC=dtu,DC=dk']
    

    search_attributes = ['cn', 'mail', 'sAMAccountName', 'distinguishedName', 'userPrincipalName', 'memberOf']
    users_first_100_with_attributes = users_first_100 = active_directory_query(base_dn=base_dn, search_filter=search_filter, search_attributes=search_attributes, limit=limit)
    print(len(users_first_100_with_attributes))
    print(users_first_100_with_attributes[0]['distinguishedName']) # >> CN=Exchange Online-ApplicationAccount,OU=Users,OU=MailogKalender,OU=BIT-DSG,OU=AIT,DC=win,DC=dtu,DC=dk
    

    search_filter = "(objectClass=computer)"
    limit = 100  

    computers_first_100 = active_directory_query(base_dn=base_dn, search_filter=search_filter, limit=limit)
    print(len(computers_first_100))
    print(computers_first_100[0]['distinguishedName'])

    search_attributes = ['cn', 'description', 'distinguishedName', 'operatingSystem', 'operatingSystemVersion']
    computers_first_100_with_attributes = active_directory_query(base_dn=base_dn, search_filter=search_filter, search_attributes=search_attributes, limit=limit)
    print(len(computers_first_100_with_attributes))
    print(computers_first_100_with_attributes[0]['distinguishedName'])


    # get first 100 groups
    search_filter = "(objectClass=group)"
    limit = 100 
    groups_first_100 = active_directory_query(base_dn=base_dn, search_filter=search_filter, limit=limit)
    print(len(groups_first_100))
    print(groups_first_100[0]['distinguishedName'])

    search_attributes = ['cn', 'description', 'distinguishedName', 'member']
    groups_first_100_with_attributes = active_directory_query(base_dn=base_dn, search_filter=search_filter, search_attributes=search_attributes, limit=limit)
    print(len(groups_first_100_with_attributes))
    print(groups_first_100_with_attributes[0]['distinguishedName'])

    # get first 100 groups that is under 'OU=IT,OU=Groups,OU=SUS,OU=Institutter,DC=win,DC=dtu,DC=dk'
    base_dn = "OU=IT,OU=Groups,OU=SUS,OU=Institutter,DC=win,DC=dtu,DC=dk"
    search_filter = "(objectClass=group)"
    limit = 100
    groups_first_100 = active_directory_query(base_dn=base_dn, search_filter=search_filter, limit=limit)
    print(len(groups_first_100))
    print(groups_first_100[0]['distinguishedName'])

    print('Done')


if __name__ == "__main__":
    run()


