def run_assistant_query(user_query):
    import os
    import openai
    import json
    import requests
    from active_directory.services import execute_active_directory_query
    from datetime import datetime, date
    from django.conf import settings
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(dotenv_path=find_dotenv())

    openai.api_key = os.getenv("OPENAI_API_KEY")
    admin_api_key = os.getenv("DJANGO_SUPERUSER_APIKEY")

    if settings.DEBUG:
        swagger_url = 'http://localhost:6081/myview/swagger/?format=openapi'
        headers = {}
    else:
        swagger_url = 'https://api.security.ait.dtu.dk/myview/swagger/?format=openapi'
        headers = {
            'Authorization': f'{admin_api_key}'
        }

    response = requests.get(swagger_url, headers=headers)

    if response.status_code == 200:
        swagger_data = response.json()
    else:
        print("Failed to retrieve Swagger data. Status code:", response.status_code)

    active_directory_description = swagger_data['paths']['/active-directory/v1.0/query']['get']['description']

    # Include the API summary in the system prompt and add 'explanation' field
    system_prompt = (
        "You are an assistant that provides Active Directory query parameters based on user requests.\n\n"
        f"{active_directory_description}\n\n"
        "Always provide your response in JSON format with the following fields:\n"
        "- base_dn\n"
        "- search_filter\n"
        "- search_attributes\n"
        "- limit\n"
        "- excluded_attributes\n"
        "- explanation\n"
        "The 'explanation' field should contain a brief explanation of the query parameters you have generated.\n"
        "Do not include any additional text outside of the JSON format."
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": user_query
        }
    ]

    # Define the function
    functions = [
        {
            "name": "get_nt_time_from_date",
            "description": "Calculate NT time format from a given date. Useful for constructing LDAP queries with date-based filters.",
            "parameters": {
                "type": "object",
                "required": ["year"],
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "The year component of the date. Example: 2005"
                    },
                    "month": {
                        "type": "integer",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 12,
                        "description": "The month component of the date (1-12). Default is 1."
                    },
                    "day": {
                        "type": "integer",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 31,
                        "description": "The day component of the date (1-31). Default is 1."
                    }
                }
            }
        }
    ]

    # Now make the OpenAI API call
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=messages,
        functions=functions,
        function_call="auto",
        temperature=1,
        max_tokens=2048,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )

    assistant_message = response.choices[0].message

    # Initialize nt_time
    nt_time = None

    # Check for function call
    if assistant_message.get("function_call"):
        function_name = assistant_message["function_call"]["name"]
        arguments = json.loads(assistant_message["function_call"]["arguments"])

        if function_name == "get_nt_time_from_date":
            # Call the function to calculate NT time
            nt_time_result = get_nt_time_from_date(**arguments)
            nt_time = nt_time_result

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
                functions=functions,
                function_call="auto",
                temperature=1,
                max_tokens=2048,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
            )
            assistant_message = response.choices[0].message
        else:
            raise Exception(f"Function '{function_name}' is not recognized.")

    # Now, get the assistant's content and parse it as per the response format
    content = assistant_message.get("content", "")

    # Try to parse the content as JSON
    try:
        arguments = json.loads(content)
    except json.JSONDecodeError:
        raise Exception("The assistant's response is not valid JSON.")

    # Ensure all required fields are present, including 'explanation'
    required_fields = ["base_dn", "search_filter", "search_attributes", "limit", "excluded_attributes", "explanation"]
    for field in required_fields:
        if field not in arguments:
            raise Exception(f"Field '{field}' is missing from the assistant's response.")

    # If nt_time is available, replace any placeholders in search_filter
    search_filter = arguments["search_filter"]
    if "{NT_TIME}" in search_filter and nt_time is not None:
        # Replace any {NT_TIME} placeholders with the actual nt_time value
        search_filter = search_filter.replace("{NT_TIME}", str(nt_time))
        arguments["search_filter"] = search_filter

    # Now execute the Active Directory query
    query_result = execute_active_directory_query(
        base_dn=arguments["base_dn"],
        search_filter=arguments["search_filter"],
        search_attributes=[attr.strip() for attr in arguments["search_attributes"].split(",")],
        limit=arguments.get("limit"),
        excluded_attributes=[attr.strip() for attr in arguments["excluded_attributes"].split(",")]
    )

    # Convert datetime objects to strings in the query_result
    def convert_datetimes(obj):
        if isinstance(obj, dict):
            return {k: convert_datetimes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_datetimes(item) for item in obj]
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        else:
            return obj

    arguments["active_directory_query_result"] = convert_datetimes(query_result)
    arguments["number_of_returned_objects"] = len(arguments["active_directory_query_result"])

    # Generate the XLSX file and include its URL
    output_file_name = generate_generic_xlsx_document(query_result)
    arguments["xlsx_file_name"] = output_file_name
    arguments["xlsx_file_url"] = settings.MEDIA_URL + output_file_name

    # Return the arguments dictionary
    return arguments





# Define get_nt_time_from_date function
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




def generate_generic_xlsx_document(data):
    import pandas as pd
    import os
    from django.conf import settings
    from datetime import datetime

    # Extract unique keys
    unique_keys = set()
    for item in data:
        unique_keys.update(item.keys())

    # Extract data
    extracted_data = []
    for item in data:
        row = {}
        for key in unique_keys:
            value = item.get(key, "")
            if isinstance(value, list):
                row[key] = ', '.join(map(str, value))
            else:
                row[key] = value
        extracted_data.append(row)

    # Convert to DataFrame
    df = pd.DataFrame(extracted_data)

    # Generate unique file name
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_file_name = f'active_directory_query_{timestamp}.xlsx'
    output_file_path = os.path.join(settings.MEDIA_ROOT, output_file_name)

    # Save to XLSX
    df.to_excel(output_file_path, index=False)

    return output_file_name
