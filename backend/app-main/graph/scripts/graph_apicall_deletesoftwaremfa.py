from ._graph_get_bearertoken import _get_bearertoken
from ._http import graph_request
# from ._graph_get_user_authentication_methods import get_user_authentication_methods

def delete_software_mfa_method(azure_user_principal_id, authentication_method_id):
    """
    Deletes a software-based MFA method for a specified user.

    Parameters:
    - azure_user_principal_id: The Azure User Principal ID (e.g., user ID)
    - authentication_method_id: The ID of the authentication method to delete

    Returns:
    - response: The HTTP response object
    - status_code: The HTTP status code of the response
    """
    # Retrieve the bearer token
    token = _get_bearertoken()

    # Set up the headers with the bearer token
    headers = {
        'Authorization': f'Bearer {token}'
    }

    # Construct the API endpoint for deleting the software OATH MFA method
    api_endpoint = f"https://graph.microsoft.com/v1.0/users/{azure_user_principal_id}/authentication/softwareOathMethods/{authentication_method_id}"

    # Make the DELETE request to the API endpoint
    response = graph_request("DELETE", api_endpoint, headers=headers, timeout=20)

    # Return the response and status code
    return response, response.status_code

def run():
    # Example user principal ID and authentication method ID
    azure_user_principal_id = '3358461b-2b36-4019-a2b7-2da92001cf7c'
    authentication_method_id = '38870367-9eb1-4568-9056-23c141f777de'
    
    # Call the delete function and capture the response
    response, status_code = delete_software_mfa_method(azure_user_principal_id, authentication_method_id)
    
    # Print the HTTP status code
    print(status_code)

# Entry point of the script
if __name__ == "__main__":
    run()
