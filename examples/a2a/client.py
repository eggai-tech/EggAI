"""
Simple A2A Client - Connects to EggAI A2A agent and executes text-based skills.
"""

import asyncio
import logging
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    SendMessageRequest,
    MessageSendParams,
    SendMessageResponse,
    Message,
    Part,
    TextPart,
    DataPart,
    Role,
)


def extract_response_text(response: SendMessageResponse) -> str:
    """Extract text from A2A response."""
    # response: SendMessageResponse -> root: SendMessageSuccessResponse -> result: Message -> parts: List[Part]
    # The response part can be either DataPart or TextPart
    part = response.root.result.parts[0].root
    if hasattr(part, 'text'):
        return part.text
    elif hasattr(part, 'data'):
        data = part.data
        # If the data is a dict with 'result' key, extract it
        if isinstance(data, dict) and 'result' in data:
            return data['result']
        return str(data)
    else:
        return str(part)


async def main():
    """Main client function - connects to agent and executes text operations."""

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    print("🤖 EggAI A2A Text Processing Client")
    print("=" * 50)

    base_url = "http://localhost:8080"

    async with httpx.AsyncClient() as httpx_client:
        # 1. Connect to agent and get agent card
        print(f"📡 Connecting to agent at {base_url}...")
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)

        agent_card = await resolver.get_agent_card()
        print("✅ Connected successfully!")

        # 2. Print agent information
        print("\n🏷️  Agent Information:")
        print(f"   Name: {agent_card.name}")
        print(f"   Description: {agent_card.description}")
        print(f"   Version: {agent_card.version}")
        print(f"   URL: {agent_card.url}")

        # 3. Print available skills
        print(f"\n🛠️  Available Skills ({len(agent_card.skills)}):")
        for skill in agent_card.skills:
            print(f"   • {skill.id}: {skill.description}")

        # 4. Create A2A client
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        print("\n🚀 Executing Text Skills:")
        print("-" * 30)

        # 5. Test greeter skill
        print("\n1️⃣ Testing Greeter Skill...")
        names = ["Alice", "World", "Bartholomew Wellington III"]
        
        for name in names:
            greet_message = Message(
                role=Role.user,
                parts=[Part(root=TextPart(text=name))],
                message_id=uuid4().hex,
            )

            greet_request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message=greet_message, metadata={"skill_id": "greet"}
                ),
            )

            greet_response = await client.send_message(greet_request)
            response_text = extract_response_text(greet_response)
            
            print(f"   Input: '{name}'")
            print(f"   Output: '{response_text}'")
            print()

        # 6. Test reverse skill
        print("\n2️⃣ Testing Reverse Skill...")
        texts = [
            "Hello World",
            "A man a plan a canal Panama",
            "Was it a car or a cat I saw?",
        ]
        
        for text in texts:
            reverse_message = Message(
                role=Role.user,
                parts=[Part(root=TextPart(text=text))],
                message_id=uuid4().hex,
            )

            reverse_request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message=reverse_message, metadata={"skill_id": "reverse"}
                ),
            )

            reverse_response = await client.send_message(reverse_request)
            response_text = extract_response_text(reverse_response)
            
            print(f"   Input: '{text}'")
            print(f"   Output: '{response_text}'")
            print()

        # 7. Test analyze skill
        print("\n3️⃣ Testing Analyze Skill...")
        analyze_text = "The quick brown fox jumps over the lazy dog. This pangram contains every letter of the alphabet!"
        
        analyze_message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=analyze_text))],
            message_id=uuid4().hex,
        )

        analyze_request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message=analyze_message, metadata={"skill_id": "analyze"}
            ),
        )

        analyze_response = await client.send_message(analyze_request)
        response_text = extract_response_text(analyze_response)
        
        print(f"   Input: '{analyze_text}'")
        print(f"   Output:\n{response_text}")

        print("\n🎉 All tests completed!")
        print("=" * 50)
        print("The EggAI A2A text processing is working perfectly! ✨")


if __name__ == "__main__":
    asyncio.run(main())