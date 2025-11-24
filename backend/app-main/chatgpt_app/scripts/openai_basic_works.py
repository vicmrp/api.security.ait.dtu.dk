from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import os

def run():
    # Specify the environment file path
    load_dotenv(dotenv_path=find_dotenv())

    client = OpenAI()
    client.api_key = os.getenv("OPENAI_API_KEY")

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Extract the event information."},
            {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
        ]
    )

    # The response content will be a text string; handle it as needed
    response_content = completion.choices[0].message["content"]
    
    # Output the response for manual parsing
    print("Response from OpenAI:", response_content)

if __name__ == "__main__":
    run()
