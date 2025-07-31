"""
Simple A2A Client - Connects to EggAI A2A agent and executes skills.
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
    DataPart,
    Role,
)


def extract_response_data(response: SendMessageResponse):
    """Extract data from A2A response using proper A2A models."""
    # response: SendMessageResponse -> root: SendMessageSuccessResponse -> result: Message -> parts: List[Part] -> root: DataPart -> data
    return response.root.result.parts[0].root.data


async def main():
    """Main client function - connects to agent and executes actions."""

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    print("🤖 EggAI A2A Client")
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
            print(f"     Input modes: {skill.input_modes}")
            print(f"     Output modes: {skill.output_modes}")

        # 4. Create A2A client
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        print("\n🚀 Executing Skills:")
        print("-" * 30)

        # 5. Execute greet skill
        print("\n1️⃣ Testing Greet Skill...")
        greet_message = Message(
            role=Role.user,
            parts=[Part(root=DataPart(data={"name": "Alice", "language": "es"}))],
            message_id=uuid4().hex,
        )

        greet_request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message=greet_message, metadata={"skill_id": "greet"}
            ),
        )

        greet_response = await client.send_message(greet_request)

        print(f"   Input: {greet_message.parts[0].root.data}")
        response_data = extract_response_data(greet_response)
        print(f"   Output: {response_data}")
        print("   ✅ Spanish greeting received!")

        # 6. Execute calculate skill
        print("\n2️⃣ Testing Calculate Skill...")
        calc_message = Message(
            role=Role.user,
            parts=[Part(root=DataPart(data={"operation": "multiply", "a": 7, "b": 6}))],
            message_id=uuid4().hex,
        )

        calc_request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message=calc_message, metadata={"skill_id": "calculate"}
            ),
        )

        calc_response = await client.send_message(calc_request)

        print(f"   Input: {calc_message.parts[0].root.data}")
        response_data = extract_response_data(calc_response)
        print(f"   Output: {response_data}")
        print("   ✅ Calculation completed!")

        # 7. Test different language greeting
        print("\n3️⃣ Testing French Greeting...")
        french_message = Message(
            role=Role.user,
            parts=[Part(root=DataPart(data={"name": "Bob", "language": "fr"}))],
            message_id=uuid4().hex,
        )

        french_request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message=french_message, metadata={"skill_id": "greet"}
            ),
        )

        french_response = await client.send_message(french_request)

        print(f"   Input: {french_message.parts[0].root.data}")
        response_data = extract_response_data(french_response)
        print(f"   Output: {response_data}")
        print("   ✅ French greeting received!")

        # 8. Test addition operation
        print("\n4️⃣ Testing Addition...")
        add_message = Message(
            role=Role.user,
            parts=[Part(root=DataPart(data={"operation": "add", "a": 15, "b": 25}))],
            message_id=uuid4().hex,
        )

        add_request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message=add_message, metadata={"skill_id": "calculate"}
            ),
        )

        add_response = await client.send_message(add_request)

        print(f"   Input: {add_message.parts[0].root.data}")
        response_data = extract_response_data(add_response)
        print(f"   Output: {response_data}")
        print("   ✅ Addition completed!")

        print("\n🎉 All tests completed!")
        print("=" * 50)
        print("The EggAI A2A integration is working perfectly! ✨")


if __name__ == "__main__":
    asyncio.run(main())
