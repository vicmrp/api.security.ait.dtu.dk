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

def get_nt_time_for_days_ago(days_ago):
    """
    Calculate the NT time format for the date 'days_ago' days before today.
    """
    import datetime
    nt_epoch = datetime.datetime(1601, 1, 1)
    target_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
    delta = target_date - nt_epoch
    nt_time = int(delta.total_seconds() * 10000000)
    return nt_time

def run():
    openai.api_key = os.getenv("OPENAI_API_KEY")

    # Fetch the Swagger JSON from the endpoint
    swagger_url = 'http://localhost:6081/myview/swagger/?format=openapi'  # Replace with your actual URL
    response = requests.get(swagger_url)
    swagger_data = response.json()

    # The documentation is in this value
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
            "content": "Giv mig en liste med alle de brugere som ikke har skiftet password siden 2020. som starter med adm-* Vis kun brugere der ikke er disabled. Tilføj feltet ou path. Se bort fra brugere som har pwdLastSet 1601-01-01T00:00:00+00:00"
        }
    ]

    # Define the functions, including get_nt_time_for_days_ago
    functions = [
        {
            "name": "get_nt_time_from_date",
            "description": "Calculate NT time format from a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "Year component of the date. Example: 2020"
                    },
                    "month": {
                        "type": "integer",
                        "description": "Month component of the date (1-12)."
                    },
                    "day": {
                        "type": "integer",
                        "description": "Day component of the date (1-31)."
                    }
                },
                "required": ["year", "month", "day"]
            }
        },
        {
            "name": "get_nt_time_for_days_ago",
            "description": "Calculate NT time format for the date 'days_ago' days before today.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ago": {
                        "type": "integer",
                        "description": "Number of days before today. Example: 150"
                    }
                },
                "required": ["days_ago"]
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
                        "description": "Limit for number of results. Example: 1000"
                    },
                    "base_dn": {
                        "type": "string",
                        "description": "Base DN for search. Example: 'DC=win,DC=dtu,DC=dk'"
                    },
                    "search_filter": {
                        "type": "string",
                        "description": "LDAP search filter. Example: '(&(objectClass=user)(pwdLastSet<=NT_TIME))'"
                    },
                    "search_attributes": {
                        "type": "string",
                        "description": "Comma-separated list of attributes to retrieve. Example: 'cn,pwdLastSet,distinguishedName'"
                    },
                    "excluded_attributes": {
                        "type": "string",
                        "description": "Comma-separated list of attributes to exclude from the results. Default is 'thumbnailPhoto'."
                    },
                    "explanation": {
                        "type": "string",
                        "description": "A human-readable explanation of the query."
                    }
                },
                "required": [
                    "base_dn",
                    "search_filter",
                    "search_attributes",
                    "limit",
                    "excluded_attributes",
                    "explanation"
                ]
            }
        }
    ]

    # Initialize variable to store NT time
    nt_time_2020 = None

    # First API call to process the user's request
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=messages,
        functions=functions
    )

    assistant_message = response.choices[0].message

    # Process assistant's function calls
    while assistant_message.get("function_call"):
        function_name = assistant_message["function_call"]["name"]
        arguments = json.loads(assistant_message["function_call"]["arguments"])

        if function_name == "get_nt_time_from_date":
            # Call the function to calculate NT time
            nt_time_result = get_nt_time_from_date(**arguments)
            nt_time_2020 = nt_time_result

            # Append the assistant's message and function response to messages
            messages.append(assistant_message)
            messages.append({
                "role": "function",
                "name": function_name,
                "content": json.dumps({"nt_time": nt_time_result})
            })

            # Make another API call after providing the function result
            response = openai.ChatCompletion.create(
                model="gpt-4-0613",
                messages=messages,
                functions=functions
            )
            assistant_message = response.choices[0].message

        elif function_name == "generate_ad_query_parameters":
            # Since we have the structured data, print it
            arguments["explanation"] = arguments.get("explanation", "")

            # Replace placeholder with actual NT time
            search_filter = arguments["search_filter"]
            search_filter = search_filter.replace("{NT_TIME_2020}", str(nt_time_2020))
            arguments["search_filter"] = search_filter

            print(json.dumps(arguments, indent=2))
            return
        else:
            print(f"Function '{function_name}' is not recognized.")
            return

    # If no function call, output the assistant's message
    print(assistant_message["content"])

if __name__ == "__main__":
    run()
