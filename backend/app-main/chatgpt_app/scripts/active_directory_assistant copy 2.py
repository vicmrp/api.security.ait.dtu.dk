import os
import openai
import json
import requests  # To fetch the Swagger JSON

def get_nt_time_from_date(year, month=1, day=1):
    """
    Calculate the NT time format from a given date.
    """
    import datetime
    nt_epoch = datetime.datetime(1601, 1, 1)
    target_date = datetime.datetime(year, month, day)
    delta = target_date - nt_epoch
    nt_time = int(delta.total_seconds() * 10000000)
    return nt_time

def run():
    openai.api_key = os.getenv("OPENAI_API_KEY")

    # Fetch the Swagger JSON from the endpoint
    swagger_url = 'http://localhost:6081/myview/swagger/?format=openapi'  # Replace with your actual URL
    response = requests.get(swagger_url)
    swagger_data = response.json()

    ## the documentation is in this value
    active_directory_description = swagger_data['paths']['/active-directory/v1.0/query']['get']['description']
    

    # Include the API summary in the system prompt
    system_prompt = (
        "You are an assistant that provides Active Directory query parameters based on user requests. "
        "Here is the API information:\n\n"
        f"{active_directory_description}\n"
        "Use this information to help answer the user's requests."
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": "Give me all pc's where lastlogin is more that a month a go"
        }
    ]

    # Define the functions
    functions = [
        {
            "name": "get_nt_time_from_date",
            "description": "Calculate NT time format from a given date. Useful for constructing LDAP queries with date-based filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "The year component of the date. Example: 2005"
                    },
                    "month": {
                        "type": "integer",
                        "description": "The month component of the date (1-12). Default is 1.",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 12
                    },
                    "day": {
                        "type": "integer",
                        "description": "The day component of the date (1-31). Default is 1.",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 31
                    }
                },
                "required": ["year"],
                "additionalProperties": False
            }
        },
        {
            "name": "generate_ad_query_parameters",
            "description": "Generate Active Directory query parameters based on user input.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Limit for number of results. Example: 100"
                    },
                    "base_dn": {
                        "type": "string",
                        "description": "Base DN for search. Example: 'DC=win,DC=dtu,DC=dk'"
                    },
                    "search_filter": {
                        "type": "string",
                        "description": "LDAP search filter. Example: '(objectClass=user)'"
                    },
                    "search_attributes": {
                        "type": "string",
                        "description": "Comma-separated list of attributes to retrieve, or 'ALL_ATTRIBUTES' to fetch all. Example: 'cn,mail'"
                    },
                    "excluded_attributes": {
                        "type": "string",
                        "description": "Comma-separated list of attributes to exclude from the results. Default is 'thumbnailPhoto'. Example: 'thumbnailPhoto,someOtherAttribute'"
                    }
                },
                "required": [
                    "base_dn",
                    "search_filter",
                    "search_attributes",
                    "limit",
                    "excluded_attributes"
                ],
                "additionalProperties": False
            }
        }
    ]

    # First API call
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=messages,
        functions=functions
    )

    assistant_message = response.choices[0].message

    # Check if the assistant wants to call a function
    if assistant_message.get("function_call"):
        function_name = assistant_message["function_call"]["name"]
        arguments = json.loads(assistant_message["function_call"]["arguments"])

        if function_name == "get_nt_time_from_date":
            nt_time = get_nt_time_from_date(**arguments)

            # Append the assistant's message and function response to messages
            messages.append(assistant_message)
            messages.append({
                "role": "function",
                "name": function_name,
                "content": json.dumps({"nt_time": nt_time})
            })

            # Second API call
            final_response = openai.ChatCompletion.create(
                model="gpt-4-0613",
                messages=messages,
                functions=functions
            )

            assistant_message = final_response.choices[0].message

            # Check if the assistant wants to call another function
            if assistant_message.get("function_call"):
                function_name = assistant_message["function_call"]["name"]
                arguments = json.loads(assistant_message["function_call"]["arguments"])

                if function_name == "generate_ad_query_parameters":
                    # Since we have the structured data, print it
                    print(json.dumps(arguments, indent=2))
                    return
                else:
                    print(f"Function '{function_name}' is not recognized.")
            else:
                # Output the assistant's final message
                print(assistant_message["content"])
        else:
            print(f"Function '{function_name}' is not recognized.")
    else:
        # If no function call, output the assistant's message
        print(assistant_message["content"])

if __name__ == "__main__":
    run()
