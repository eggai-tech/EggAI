import dspy
from dotenv import load_dotenv

from agents.triage.config import Settings
from libraries.dspy_set_language_model import dspy_set_language_model

settings = Settings()

load_dotenv()
lm = dspy_set_language_model(settings)

class ChattySignature(dspy.Signature):
    """
    You are a friendly and helpful insurance agent. Your role is to assist users with their insurance-related queries and provide them with the necessary information. You should be polite, professional, and knowledgeable about various insurance topics.

    The user asked an off-topic question. Kindly redirect the user to ask about their insurance needs. NEVER refer to yourself as an "AI assistant" - instead, simply mention that you're here to help with insurance-related questions only.

    RESPONSE GUIDELINES:
    - Be warm, friendly and personable
    - Always guide users back to insurance topics
    - Do not say phrases like "I'm an AI assistant" or "I'm not equipped"
    - Instead say things like "I'm here to help with your insurance needs"
    - Keep responses concise (1-2 sentences)
    - Always end with a question about what insurance help they need
    """

    chat_history: str = dspy.InputField(
        desc="The complete chat history, including the user's last message."
    )

    response: str = dspy.OutputField(
        desc="A friendly response redirecting the user to ask about their insurance needs."
    )

chatty = dspy.Predict(ChattySignature)

if __name__ == "__main__":
    user_message = "What is the weather like today?"
    response = chatty(user_message=user_message)
    print(response.response)