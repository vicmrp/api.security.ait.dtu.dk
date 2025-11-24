from myview.models import OrganizationalUnit, UserGroup

def create_user_groups_from_ous():
    target_canonical_name = "win.dtu.dk/DTUBaseUsers"
    # Query for all OrganizationalUnits with the specified canonical name pattern
    ous = OrganizationalUnit.objects.filter(canonical_name__startswith=target_canonical_name)
    for ou in ous:
        # Extract the name segment for the UserGroup
        name_parts = ou.canonical_name.split('/')
        if len(name_parts) > 2:  # Ensure there's a segment after DTUBaseUsers
            group_name = name_parts[-1]  # The part of the canonical name to use as the group name
            # Check if the UserGroup exists, if not, create it
            UserGroup.objects.get_or_create(name=group_name)



def run():
    create_user_groups_from_ous()

# if main 
if __name__ == "__main__":
    run()
