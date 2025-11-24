


def user_have_onpremises_adm_account(user_principal_name: str):

    username = user_principal_name.split('@')[0]


    from active_directory.services import execute_active_directory_query
    base_dn = "DC=win,DC=dtu,DC=dk"
    search_filter = f"(sAMAccountName=adm-{username}*)"
    active_directory_response = execute_active_directory_query(base_dn=base_dn, search_filter=search_filter)


    if not len(active_directory_response) >= 1:
        return False
    else:
        return True
    


def run():
    user = 'dast@dtu.dk'
    result = user_have_onpremises_adm_account(user)
    print(result)


if __name__ == '__main__':
    run()

