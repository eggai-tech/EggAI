"""
Agent-to-Agent (A2A) Communication Demo

This example demonstrates how to:
1. Expose an agent via HTTP API using agent.to_a2a()
2. Connect to a remote agent and send messages
3. Discover agent capabilities

Requirements:
    pip install fastapi uvicorn httpx
"""

import asyncio
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport, InMemoryTransport


async def main():
    """Demo A2A functionality"""
    
    # Set up transport
    eggai_set_default_transport(lambda: InMemoryTransport())
    
    # Create the first agent that will be exposed via A2A
    server_agent = Agent("OrderProcessingAgent")
    orders_channel = Channel("orders")
    
    @server_agent.subscribe(channel=orders_channel)
    async def handle_order(order_data):
        print(f"📦 Order received: {order_data}")
        # Simulate processing
        await asyncio.sleep(0.1)
        print(f"✅ Order {order_data.get('order_id')} processed!")
    
    @server_agent.subscribe()  # Default channel
    async def handle_status_check(message):
        if message.get("type") == "ping":
            print("🏓 Pong! Agent is alive")
    
    # Start the A2A server
    print("🚀 Starting A2A server...")
    try:
        server = await server_agent.to_a2a(host="0.0.0.0", port=8080)
        print("✅ A2A Server running at http://localhost:8080")
        
        # Give server a moment to start
        await asyncio.sleep(1)
        
        # Now create a remote agent client to interact with it
        print("\n🔗 Connecting to remote agent...")
        
        try:
            from eggai.a2a import RemoteAgent
            
            async with RemoteAgent("http://localhost:8080") as remote:
                # Get agent info
                print("📋 Getting agent info...")
                info = await remote.get_info()
                print(f"   Agent Name: {info.name}")
                print(f"   Channels: {info.channels}")
                
                # Check agent status
                status = await remote.get_status()
                print(f"   Status: {status.agent.status}")
                print(f"   Uptime: {status.uptime_seconds:.1f}s")
                
                # Send a ping message
                print("\n📤 Sending ping message...")
                result = await remote.publish_message(
                    channel="eggai.channel",
                    message={"type": "ping", "from": "remote_client"}
                )
                print(f"   Message sent: {result.success}")
                
                # Send an order
                print("\n📤 Sending order...")
                order_result = await remote.publish_message(
                    channel="orders",
                    message={
                        "order_id": "ORD-001",
                        "customer": "Alice",
                        "items": ["laptop", "mouse"],
                        "total": 1299.99
                    }
                )
                print(f"   Order sent: {order_result.success}")
                
                # Wait a bit to see the processing
                await asyncio.sleep(1)
                
                # Check updated status
                status = await remote.get_status()
                print(f"\n📊 Final message count: {status.message_count}")
        
        except ImportError:
            print("❌ A2A functionality requires: pip install fastapi uvicorn httpx")
            print("📝 Server is running, but can't demo client without dependencies")
            
            # Keep server running for manual testing
            print("\n🔄 Server running... Press Ctrl+C to stop")
            print("   Try: curl http://localhost:8080/agent/info")
            await asyncio.sleep(30)  # Run for 30 seconds
        
    except ImportError:
        print("❌ A2A functionality requires: pip install fastapi uvicorn httpx")
        return
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        if 'server' in locals():
            print("\n🛑 Stopping server...")
            await server.stop()
        print("✅ Demo completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"❌ Demo failed: {e}")