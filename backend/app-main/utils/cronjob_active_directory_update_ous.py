from utils import active_directory_connect
from ldap3.core.exceptions import LDAPKeyError
from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, ALL
import ldap3
from datetime import datetime, timedelta, timezone
from myview.models import OrganizationalUnit

















def convert_dn_to_canonical(distinguished_name):
    # Split the distinguished name by commas
    parts = distinguished_name.split(',')

    # Initialize lists to hold OU and DC components separately
    ous = []
    dcs = []

    # Iterate through each part and classify it as OU or DC
    for part in parts:
        # Each part is expected to be in the form of "TYPE=value"
        type, value = part.split('=')
        if type == "OU":
            ous.append(value)
        elif type == "DC":
            dcs.append(value)

    # Join the DC components with dots and OU components with slashes
    dc_component = '.'.join(dcs)
    ou_component = '/'.join(reversed(ous))

    # Format the canonical name by combining DC and OU components
    canonical_name = f"{dc_component}/{ou_component}"

    return canonical_name












































def update_ous():
    # Connect to Active Directory
    conn, message = active_directory_connect.active_directory_connect()

    if not conn:
        print('Failed to connect to AD:', message)
        return

    # Bind to the server
    if not conn.bind():
        print('Error in bind', conn.result)
        return

    # Define search parameters
    base_dn = "DC=win,DC=dtu,DC=dk"
    search_filter = "(objectClass=organizationalUnit)"
    search_attributes = ["distinguishedName", "name", "description"]
    page_size = 500
    paged_cookie = None

    # Create a set of all OUs in the Django model
    existing_ous = set(OrganizationalUnit.objects.values_list('distinguished_name', flat=True))
    OrganizationalUnit.objects.filter(distinguished_name__in=existing_ous).delete()

    # Perform a paged search
    more_pages = True
    while more_pages:
        conn.search(search_base=base_dn,
                    search_filter=search_filter,
                    search_scope=ldap3.SUBTREE,
                    attributes=search_attributes,
                    paged_size=page_size,
                    paged_cookie=paged_cookie)

        for entry in conn.entries:
            # Extract the distinguishedName and use it as the OU string
            distinguished_name = entry.distinguishedName.value
            # canonical_name = distinguished_name # for example convert OU=Institutter,DC=win,DC=dtu,DC=dk into win.dtu.dk/Institutter
            canonical_name = convert_dn_to_canonical(distinguished_name)
            # or convert OU=BYG,OU=Institutter,DC=win,DC=dtu,DC=dk into  win.dtu.dk/Institutter/BYG


            try:
                # Try to create a new OrganizationalUnit entry, skip if it already exists
                ou, created = OrganizationalUnit.objects.get_or_create(distinguished_name=distinguished_name, canonical_name=canonical_name)
                if created:
                    print(f"Added new OU: {distinguished_name}")

                # Remove the OU from the set of existing OUs
                existing_ous.discard(distinguished_name)
            except Exception as e:
                print(f"Error adding OU {distinguished_name}: {e}")

        more_pages = bool(conn.result['controls']['1.2.840.113556.1.4.319']['value']['cookie'])
        if more_pages:
            paged_cookie = conn.result['controls']['1.2.840.113556.1.4.319']['value']['cookie']
        else:
            paged_cookie = None

    # Delete any OUs that were not synced from Active Directory
    OrganizationalUnit.objects.filter(distinguished_name__in=existing_ous).delete()

    # Add the base_dn as an OrganizationalUnit
    OrganizationalUnit.objects.get_or_create(distinguished_name=base_dn, canonical_name='DC_win.dtu.dk')

    conn.unbind()
    print("Completed updating OUs.")



def run():
    update_ous()
    print('done')




# if main 
if __name__ == "__main__":
    run()
