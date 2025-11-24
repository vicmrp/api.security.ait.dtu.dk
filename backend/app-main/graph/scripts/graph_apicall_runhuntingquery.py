import pyodbc
import os
import json
import time
from dotenv import load_dotenv, find_dotenv
from ._graph_get_bearertoken import _get_bearertoken
from ._http import graph_request

# # Function to generate a new token
# def _generate_new_token():
#     # Replace this with your actual logic to generate a new token

#     url = 'https://login.microsoftonline.com/' + os.getenv("AZURE_TENENT_ID") + '/oauth2/token'

#     data = {
#         'resource': os.getenv("GRAPH_RESOURCE"),
#         'client_id': os.getenv("DEFENDER_CLIENT_ID"),
#         'client_secret': os.getenv("DEFENDER_CLIENT_SECRET"),
#         'grant_type': 'client_credentials'
#     }

#     response = requests.post(url, data=data)

#     if response.status_code == 200:
#         return response.json()['access_token']
#     else:
#         return None



# Load environment variables from .env file
load_dotenv(dotenv_path=find_dotenv())

def run_hunting_query(query):




    
    
    # Use the token to perform the hunting query
    token = _get_bearertoken()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }


    # Define the API endpoint
    api_endpoint = "https://graph.microsoft.com/v1.0/security/runHuntingQuery"  # Replace with your actual endpoint

    # Make the request
    response = graph_request("POST", api_endpoint, headers=headers, json={"Query": query}, timeout=20)

    return response, response.status_code









def run():
    # # Generate a new token
    # new_token = generate_new_token()
    # message = new_token
    # print(message)

    kql = "// might contain sensitive data\nlet alertedEvent = datatable(compressedRec: string)\n['eAEtjkFPAjEQRv8K6RmabReF3ZNEohiMEEQP3up22Excps20S9IY/7tj5DjvvWS+b3XEMzwCAbsMXrXKVraeGTOrq6OZt2bRmrk2y4Wtbm8+1FStYlxjioMrL+4M0u9OJ+xgE+SYqrcEvGekDqMbrsEFO4Y7n0ftvyR52q+8Z0hJlGmsrpe6qbSxjbh7zEXwNlAPlCbPhfrPIvw1yzgRm3ABn7LzQH91GClz2fEBegwkfr0V/DAOA/2/fscuB54cAOPI6ucXbMZKOg==']\n| extend raw = todynamic(zlib_decompress_from_base64_string(compressedRec)) | evaluate bag_unpack(raw) | project-away compressedRec;\nalertedEvent"
    response = run_hunting_query(kql)
    print(response)



# if main 
if __name__ == "__main__":
    run()
