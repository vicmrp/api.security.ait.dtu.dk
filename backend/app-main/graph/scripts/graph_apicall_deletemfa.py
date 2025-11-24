
from ._graph_get_bearertoken import _get_bearertoken
from ._http import graph_request
# from ._graph_get_user_authentication_methods import get_user_authentication_methods


def microsoft_authentication_method(azure_user_principal_id ,authentication_method_id):

    token = _get_bearertoken()

    headers = {
        'Authorization': f'Bearer {token}'
    }




    # before you delete make sure that it is not the password method. By checking if @odata.type not contains password




    
    # https://graph.microsoft.com/v1.0/users/vicre-test01@dtudk.onmicrosoft.com/authentication/microsoftAuthenticatorMethods/123e4441-eadf-4950-883d-fea123988824
    api_endpoint = f"https://graph.microsoft.com/v1.0/users/{azure_user_principal_id}/authentication/microsoftAuthenticatorMethods/{authentication_method_id}"
    

    response = graph_request("DELETE", api_endpoint, headers=headers, timeout=20)

    # response.status_code = 204
     
    # 204 means successfully deleted
    return response, response.status_code




def run():
    azure_user_principal_id = '3358461b-2b36-4019-a2b7-2da92001cf7c'
    authentication_method_id = 'f18a98ad-7fc4-4294-8814-4fbdea4ef13b'
    response, status_code = microsoft_authentication_method(azure_user_principal_id, authentication_method_id)
    # print(response)
    print(status_code)



# if main 
if __name__ == "__main__":
    run()

