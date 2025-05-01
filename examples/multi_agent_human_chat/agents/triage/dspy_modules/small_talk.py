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
    The user asked an off-topic question. Kindly redirect the user to ask about their insurance needs, specifying that you are not a human and cannot answer those questions.
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