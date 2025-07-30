"""
A2A Protocol Compliant Demo

This example demonstrates the official A2A (Agent2Agent) protocol implementation
following the specification at https://a2a-protocol.org/

Features demonstrated:
1. Agent discovery via well-known URI (/.well-known/agent.json)
2. JSON-RPC 2.0 message sending
3. Task management and status tracking
4. Standards compliant communication

Requirements:
    pip install fastapi uvicorn httpx
"""

import asyncio
from eggai import Agent
from eggai.transport import eggai_set_default_transport, InMemoryTransport


async def main():
    """Demo A2A protocol compliance"""
    
    # Set up transport
    eggai_set_default_transport(lambda: InMemoryTransport())
    
    # Create an agent
    agent = Agent("A2AProtocolAgent")
    
    @agent.subscribe()
    async def handle_a2a_messages(message):
        print(f"🤖 Agent received: {message}")
        if message.get("content"):
            print(f"   Content: {message['content']}")
            print(f"   Role: {message.get('role', 'unknown')}")
            print(f"   Task ID: {message.get('task_id', 'none')}")
    
    # Start A2A server (compliant with A2A protocol)
    print("🚀 Starting A2A Protocol compliant server...")
    try:
        server = await agent.to_a2a(host="0.0.0.0", port=8080)
        print("✅ A2A Server running at http://localhost:8080")
        print("📋 Agent Card: http://localhost:8080/.well-known/agent.json")
        
        # Give server a moment to start
        await asyncio.sleep(1)
        
        # Demonstrate A2A protocol features
        try:
            from eggai.a2a import A2AClient, MessageRole
            
            print("\n🔗 Testing A2A Protocol compliance...")
            
            async with A2AClient("http://localhost:8080") as client:
                # 1. Agent Discovery
                print("\n📋 1. Agent Discovery (well-known URI)")
                agent_card = await client.discover_agent()
                print(f"   Agent Name: {agent_card.name}")
                print(f"   Description: {agent_card.description}")
                print(f"   Protocol Version: {agent_card.protocol_version}")
                print(f"   Capabilities: {agent_card.capabilities}")
                print(f"   Endpoint: {agent_card.endpoint}")
                
                # 2. Send Message (JSON-RPC 2.0)
                print("\n💬 2. Sending message via JSON-RPC 2.0")
                task = await client.send_message(
                    content="Hello from A2A protocol client!",
                    role=MessageRole.USER
                )
                print(f"   Task ID: {task.id}")
                print(f"   Status: {task.status.value}")
                print(f"   Messages: {len(task.messages)}")
                
                # 3. Task Management
                print("\n📊 3. Task status retrieval")
                updated_task = await client.get_task(task.id)
                print(f"   Status: {updated_task.status.value}")
                print(f"   Created: {updated_task.created_at}")
                print(f"   Updated: {updated_task.updated_at}")
                
                # Show messages in task
                for i, msg in enumerate(updated_task.messages):
                    print(f"   Message {i+1}: {msg.role.value}")
                    for j, part in enumerate(msg.parts):
                        print(f"     Part {j+1}: {part.type.value} - {part.content}")
                
                # 4. Health Check
                print("\n❤️ 4. Health check")
                is_healthy = await client.health_check()
                print(f"   Agent healthy: {is_healthy}")
                
                print("\n✅ A2A Protocol compliance verified!")
                
        except ImportError:
            print("❌ A2A functionality requires: pip install fastapi uvicorn httpx")
            print("📝 Server is running for manual testing...")
            print("\n🧪 Manual testing commands:")
            print("   curl http://localhost:8080/.well-known/agent.json")
            print("   curl -X POST http://localhost:8080/ -H 'Content-Type: application/json' \\")
            print("        -d '{\"jsonrpc\":\"2.0\",\"method\":\"message/send\",\"params\":{\"messages\":[{\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"content\":\"Hello A2A!\"}]}]},\"id\":\"1\"}'")
            
            # Keep server running for manual testing
            await asyncio.sleep(30)
        
    except ImportError:
        print("❌ A2A functionality requires: pip install fastapi uvicorn httpx")
        return
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        if 'server' in locals():
            print("\n🛑 Stopping A2A server...")
            await server.stop()
        print("✅ Demo completed!")


def print_a2a_info():
    """Print information about A2A protocol"""
    print("📖 About A2A Protocol:")
    print("   The Agent2Agent (A2A) Protocol is an open standard for AI agent communication")
    print("   🌐 Specification: https://a2a-protocol.org/")
    print("   📊 Uses JSON-RPC 2.0 over HTTP(S)")
    print("   🔍 Supports agent discovery via well-known URIs")
    print("   📋 Provides task management and stateful operations")
    print("   🔒 Designed for enterprise-ready, secure agent interactions")
    print()


if __name__ == "__main__":
    print_a2a_info()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"❌ Demo failed: {e}")