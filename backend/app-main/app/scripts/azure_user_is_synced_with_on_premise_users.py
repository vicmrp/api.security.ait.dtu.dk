

def convert_guid_to_base64(guid_str):
    import base64
    # Convert the string into bytes, assuming it's stored in escaped unicode form
    bytes_guid = bytes(guid_str, 'raw_unicode_escape')
    # Encode these bytes into a Base64 string
    base64_guid = base64.b64encode(bytes_guid)
    return base64_guid.decode('utf-8')

def convert_to_base64(byte_data):
    import base64
    return base64.b64encode(byte_data).decode('utf-8')

def azure_user_is_synced_with_on_premise_users(sam_accountname: str, on_premises_immutable_id: str):
    
    from active_directory.services import execute_active_directory_query
    base_dn = "DC=win,DC=dtu,DC=dk"
    search_filter = f"(sAMAccountName={sam_accountname})"
    search_attributes = ['mS-DS-ConsistencyGuid']
    active_directory_response = execute_active_directory_query(base_dn=base_dn, search_filter=search_filter, search_attributes=search_attributes)

    try:
        ms_ds_consistency_guid = convert_to_base64(active_directory_response[0]['mS-DS-ConsistencyGuid'][0])
    except IndexError:
        return False

    is_synced = (ms_ds_consistency_guid == on_premises_immutable_id) # Compare the two base64 strings

    if is_synced:
        return True
    else:
        return False
    


def run():
    from graph.services import execute_get_user
    from django.http import JsonResponse

    # This part is equal to when the user has authenticated via msal
    
    sam_accountname = 'vicre'
    azure_user_principal_name = sam_accountname + '@dtu.dk'
    select_param = '$select=onPremisesImmutableId'
    response, status_code = execute_get_user(azure_user_principal_name, select_param)
    if status_code != 200:
        print('User not found in azure')
    

    on_premises_immutable_id = response.get('onPremisesImmutableId')
    is_synced = azure_user_is_synced_with_on_premise_users(sam_accountname=sam_accountname, on_premises_immutable_id=on_premises_immutable_id)

    if is_synced:
        print('User is authenticated')
    else:
        print('User is not authenticated')



    # if django_user is not None:
    #     return JsonResponse({'status': 'success', 'message': 'User is authenticated'})
    # else:
    #     return JsonResponse({'status': 'error', 'message': 'User is not authenticated'})




    pass

    # from django.contrib.auth.models import User
    # user = User.objects.get(username='dast')
    # print(validate_user(user))


if __name__ == '__main__':
    run()

