
import requests, json
from ._defender_get_bearertoken import _get_bearertoken


def get_machine(*, computer_dns_name, select_parameters=None):

    # Microsoft api documentation
    # https://learn.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0&tabs=http    

    token = _get_bearertoken()

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }


    if select_parameters is not None:
        api_endpoint = f"https://api.securitycenter.microsoft.com/api/machines/{computer_dns_name}?{select_parameters}"
    else:
        api_endpoint = f"https://api.securitycenter.microsoft.com/api/machines/{computer_dns_name}"

    response = requests.get(api_endpoint, headers=headers)



    return json.loads(response.text), response.status_code




def run():
    computer_dns_name = 'DTU-5CG0469JZS.win.dtu.dk'
    # user_principal_name = 'adm-vicre-not-a-real-user@dtu.dk'    # will return status 404
    response, status_code = get_machine(computer_dns_name=computer_dns_name, select_parameters='$select=id,lastSeen')
    
    print(response.get('id'))
    print(response.get('lastSeen'))



# if main 
if __name__ == "__main__":
    run()

