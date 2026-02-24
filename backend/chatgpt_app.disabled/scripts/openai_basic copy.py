from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import os, requests, json


def run():

    # http://localhost:6081/myview/swagger/?format=openapi
    # get documentation from the swagger file
    # extract active-directory endpoint





    # Example usage
    swagger_url = "http://localhost:6081/myview/swagger/?format=openapi"
    path = "/active-directory/v1.0/query"
    endpoint_doc = get_endpoint_documentation(swagger_url, path)

    # Extract the relevant data from endpoint_doc
    description = endpoint_doc['get']['description']
    parameters = endpoint_doc['get']['parameters']
    responses = endpoint_doc['get']['responses']

    # Create an object containing description, parameters, and responses
    endpoint_info = {
        "description": description,
        "parameters": parameters,
        "responses": responses
    }

    # Convert the object to a JSON string
    endpoint_info_json = json.dumps(endpoint_info, indent=4)



    # # Example usage with keyword arguments
    message = get_openai_completion(
        system="endpoint_info_json",
        user="Give me a list of all users, with their username, when they last logged in, and when they last set their password, across the entire domain."
    )

    # Give me a query that returns all user where pwdLastSet is before 2024. The object should be of type user

    # print(message.content)




if __name__ == "__main__":
    run()




def get_openai_completion(system: str, user: str):
    load_dotenv(dotenv_path=find_dotenv())

    # Create OpenAI client and set the API key
    client = OpenAI()
    client.api_key = os.getenv("OPENAI_API_KEY")

    # Create completion using the OpenAI API
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    )

    # Print the message from the response
    return completion.choices[0].message


def get_endpoint_documentation(swagger_url: str, path: str):
    # Fetch the Swagger JSON from the provided URL
    response = requests.get(swagger_url)
    
    # Check if the request was successful
    if response.status_code != 200:
        raise Exception(f"Failed to fetch Swagger JSON. Status code: {response.status_code}")
    
    # Parse the JSON response
    swagger_json = response.json()

    # Find and return the documentation for the specified path
    endpoint_doc = swagger_json.get('paths', {}).get(path)
    
    if endpoint_doc:
        return endpoint_doc
    else:
        return None
