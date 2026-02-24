import os

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
    import openai
    import json

    openai.api_key = os.getenv("OPENAI_API_KEY")

    response = openai.ChatCompletion.create(
        model="gpt-4-0613",  # Updated model name to a function-calling capable model
        messages=[
            {
                "role": "system",
                "content": "You are an assistant that provides Active Directory query parameters based on user requests."
            },
            {
                "role": "user",
                "content": "Give me all users that have a password older than 2010."
            }
        ],
        temperature=1,
        max_tokens=2048,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        tools=[
            {
                "type": "function",
                "function": {
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
                        "required": [
                            "year"
                        ],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            }
        ],
        parallel_tool_calls=True,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "active_directory_response",
                "schema": {
                    "type": "object",
                    "required": [
                        "base_dn",
                        "search_filter",
                        "search_attributes",
                        "limit",
                        "excluded_attributes"
                    ],
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
                    "additionalProperties": False
                },
                "strict": True
            }
        }
    )

    # Process the assistant's response
    assistant_message = response.choices[0].message

    # Check if the assistant wants to call a function
    if assistant_message.get("tool_calls"):
        for tool_call in assistant_message["tool_calls"]:
            function_name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])

            # Execute the function if it's 'get_nt_time_from_date'
            if function_name == "get_nt_time_from_date":
                nt_time = get_nt_time_from_date(**arguments)

                # Prepare the function result message
                function_result_message = {
                    "role": "tool",
                    "content": json.dumps({"nt_time": nt_time}),
                    "tool_call_id": tool_call["id"]
                }

                # Append the function result to the messages
                messages = [
                    {
                        "role": "system",
                        "content": "You are an assistant that provides Active Directory query parameters based on user requests."
                    },
                    {
                        "role": "user",
                        "content": "Give me all users that have a password older than 2010."
                    },
                    assistant_message,  # Assistant's function call
                    function_result_message  # Function result
                ]

                # Call the API again to get the final response
                final_response = openai.ChatCompletion.create(
                    model="gpt-4-0613",
                    messages=messages,
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "get_nt_time_from_date",
                                "description": "Calculate NT time format from a given date.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "year": {"type": "integer"},
                                        "month": {"type": "integer"},
                                        "day": {"type": "integer"}
                                    },
                                    "required": ["year"],
                                    "additionalProperties": False
                                },
                                "strict": False
                            }
                        }
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "active_directory_response",
                            "schema": {
                                "type": "object",
                                "required": [
                                    "base_dn",
                                    "search_filter",
                                    "search_attributes",
                                    "limit",
                                    "excluded_attributes"
                                ],
                                "properties": {
                                    "limit": {"type": "integer"},
                                    "base_dn": {"type": "string"},
                                    "search_filter": {"type": "string"},
                                    "search_attributes": {"type": "string"},
                                    "excluded_attributes": {"type": "string"}
                                },
                                "additionalProperties": False
                            },
                            "strict": True
                        }
                    }
                )

                # Output the assistant's final message
                print(final_response.choices[0].message["parsed"])
                return
    else:
        # If no function call is made, just print the assistant's message
        print(assistant_message["content"])

if __name__ == "__main__":
    run()
