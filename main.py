import os
import chainlit as cl
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import requests
import json

# Load environment variables
load_dotenv()

# Initialize Language Model
llm = ChatOpenAI(
    model_name="gpt-3.5-turbo",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)


@cl.on_chat_start
async def start():
    await cl.Message(content="Hello! How can I help you?").send()


@cl.on_message
async def main(message: cl.Message):
    # OpenAI API endpoint
    url = "https://api.openai.com/v1/chat/completions"

    # Headers with your API key
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}"
    }

    # Request data
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": message.content}],
        "temperature": 0.7
    }

    # Make the API call
    response = requests.post(url, headers=headers, data=json.dumps(data))

    # Parse the response
    response_json = response.json()
    response_text = response_json["choices"][0]["message"]["content"]

    # Send response back to user
    await cl.Message(content=response_text).send()

if __name__ == "__main__":
    cl.run()
