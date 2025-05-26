from typing import AsyncIterable, Union

import dspy
from dotenv import load_dotenv
from dspy import Prediction
from dspy.streaming import StreamResponse

from agents.triage.config import Settings
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.tracing import init_telemetry

settings = Settings()

load_dotenv()
lm = dspy_set_language_model(settings)


class ChattySignature(dspy.Signature):
    """
    You are a friendly and helpful insurance agent. Your role is to assist new and existing customers with their insurance-related queries and provide them with the necessary information. You should be polite, professional, and knowledgeable about various insurance topics.

    The user asked an off-topic question. Kindly redirect the user to ask about their insurance and insurance support needs. NEVER refer to yourself as an "AI assistant" - instead, simply mention that you're here to help with insurance-related questions only.

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

def chatty(chat_history: str) -> AsyncIterable[Union[StreamResponse, Prediction]]:
    return dspy.streamify(
        dspy.Predict(ChattySignature),
        stream_listeners=[
            dspy.streaming.StreamListener(signature_field_name="response"),
        ],
        include_final_prediction_in_output_stream=True,
        is_async_program=False,
        async_streaming=True
    )(chat_history=chat_history)

if __name__ == "__main__":
    async def openlit_async_stream_bug():
        init_telemetry(app_name=settings.app_name)
        import litellm

        chunks = await litellm.acompletion(
            model="openai/gpt-4o",
            messages=[{"content": "Hello, what is the meaning of life. Tell me.", "role": "user"}],
            stream=True,
        )

        async for chunk in chunks:
            content = chunk.choices[0].delta.content
            if content:
                print(content, end='')
            else:
                print("")
                print(chunk)

    async def run():
        output = chatty(chat_history="User: Hello.")
        async for msg in output:
            if isinstance(msg, StreamResponse):
                print(msg.chunk, end='')
            if isinstance(msg, Prediction):
                print("")
                print("")
                print(msg.get_lm_usage())


    import asyncio
    asyncio.run(run())
