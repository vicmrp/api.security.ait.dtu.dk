from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import os, requests, json
from pydantic import BaseModel


# Define the Pydantic model for the structured output
class LDAPQueryFormat(BaseModel):
    base_dn: str
    search_filter: str
    search_attributes: list[str]
    limit: int
    excluded_attributes: list[str]

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




    return_format = (
        "{\n"
        "  \"Base DN\": \"DC=win,DC=dtu,DC=dk\",\n"
        "  \"Search Filter\": \"(objectClass=user)\",\n"
        "  \"Search Attributes\": \"cn, pwdLastSet\",\n"
        "  \"Limit\": \"100\",\n"
        "  \"Excluded Attributes\": \"thumbnailPhoto\"\n"
        "}"
    )


    # # Example usage with keyword arguments
    response_json = get_openai_completion(
        system=endpoint_info_json,
        user="Give me a query that returns all users where pwdLastSet is before 2024. The object should be of type user.",
        response_format=LDAPQueryFormat
    )

    response_object = json.loads(response_json)

    print(response_object)

if __name__ == "__main__":
    run()




def get_openai_completion(system: str, user: str, response_format):
    # Specify the environment file path
    load_dotenv(dotenv_path=find_dotenv())

    # Create OpenAI client and set the API key
    client = OpenAI()
    client.api_key = os.getenv("OPENAI_API_KEY")

    # Modify the user prompt to include the return format
    user_prompt = (
        f"{user}"
    )

    # Create completion using the OpenAI API
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        response_format=response_format,
    )

    # Return the message content from the response
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
    
    
