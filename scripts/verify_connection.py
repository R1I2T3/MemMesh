import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini

load_dotenv()


def check_connection() -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY is not set in environment.")

    agent = Agent(model=Gemini(id="gemini-2.5-flash"))
    response = agent.run("Reply with: connection verified")
    return response.content


if __name__ == "__main__":
    result = check_connection()
    print(f"✅ Gemini API connected: {result}")
