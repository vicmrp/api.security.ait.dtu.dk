from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel
import os
import re

class Step(BaseModel):
    explanation: str
    output: str

class MathReasoning(BaseModel):
    steps: list[Step]
    final_answer: str

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

def run():
    # Load environment variables
    load_dotenv(dotenv_path=find_dotenv())

    client = OpenAI()
    client.api_key = os.getenv("OPENAI_API_KEY")



    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Extract the event information."},
            {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
        ],
        response_format=CalendarEvent,
    )

    # completion = client.chat.completions.create(
    #     model="gpt-4o",
    #     messages=[
    #         {"role": "system", "content": "You are a helpful math tutor. Guide the user through the solution step by step."},
    #         {"role": "user", "content": "How can I solve 8x + 7 = -23?"}
    #     ]
    # )

    response_content = completion.choices[0].message["content"]

    # # Output the raw response for debugging
    # print("Response from OpenAI:", response_content)

    # # Parse the response manually (adjust parsing as needed based on response format)
    # steps = []
    # step_matches = re.findall(r'Step \d+: (.*?)\nOutput: (.*?)(?=\nStep|\nFinal Answer)', response_content, re.DOTALL)
    # for explanation, output in step_matches:
    #     steps.append(Step(explanation=explanation.strip(), output=output.strip()))

    # final_answer_match = re.search(r'Final Answer: (.*)', response_content)
    # final_answer = final_answer_match.group(1).strip() if final_answer_match else "Unknown"

    # # Map parsed data to MathReasoning model
    # math_reasoning = MathReasoning(steps=steps, final_answer=final_answer)

    # print("Parsed Math Reasoning:", math_reasoning)

if __name__ == "__main__":
    run()
