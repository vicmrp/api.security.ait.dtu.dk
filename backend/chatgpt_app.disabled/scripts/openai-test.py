from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import os


def run():
    # Example usage with keyword arguments
    get_openai_completion(
        system="You return 1 ldap3 query at a time. Give me a ldap3 query that returns user name vicre >> (sAMAccountName=vicre). Do not explain the query, just provide it.",
        user="Give me a query that returns all user where pwdLastSet is before 2024. The object should be of type user"
    )




if __name__ == "__main__":
    run()




def get_openai_completion(system: str, user: str):
    load_dotenv(dotenv_path=find_dotenv())

    # Create OpenAI client and set the API key
    client = OpenAI()
    client.api_key = os.getenv("OPENAI_API_KEY")

    # Create completion using the OpenAI API
    completion = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    )

    # Print the message from the response
    print(completion.choices[0].message)
