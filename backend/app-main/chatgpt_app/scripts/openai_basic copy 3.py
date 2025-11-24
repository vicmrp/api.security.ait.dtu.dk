from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import os, requests, json
from pydantic import BaseModel
from typing import List, Optional

# Define the Pydantic model for the structured output
class LDAPQueryFormat(BaseModel):
    base_dn: str
    search_filter: str
    search_attributes: List[str]
    limit: int
    excluded_attributes: List[str]

class OpenAIResponse(BaseModel):
    refusal: Optional[str] = None
    parsed: Optional[LDAPQueryFormat] = None

def run():

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
    response_json = get_openai_completion(
        system=endpoint_info_json,
        user="Give me a query that returns all users where pwdLastSet is before 2024. The object should be of type user.",
        response_format=LDAPQueryFormat
    )

    response_object = json.loads(response_json)

    print(response_object)

if __name__ == "__main__":
    run()




def get_openai_completion(system: str, user: str, response_format: BaseModel):
    # Specify the environment file path
    load_dotenv(dotenv_path=find_dotenv())

    # Create OpenAI client and set the API key
    client = OpenAI()
    client.api_key = os.getenv("OPENAI_API_KEY")

    # Modify the user prompt to include the return format
    user_prompt = f"{user}"

    # Handle the response format as a string (if needed)
    response_format_dict = response_format.schema() if hasattr(response_format, 'schema') else {}

    # Create completion using the OpenAI API
    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # or "gpt-3.5-turbo"
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        response_format=response_format_dict  # Pass as dict or string, not a class
    )

    # Extract the relevant message from the response
    openai_response = completion.choices[0].message

    # Handle refusal if present
    if openai_response.refusal:
        print("Model refusal:", openai_response.refusal)
        return openai_response.refusal
    else:
        print("Parsed response:", openai_response.parsed)
        return openai_response.parsed




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
    
    
