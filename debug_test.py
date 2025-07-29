import asyncio
from pydantic import BaseModel
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport, KafkaTransport

class Order(BaseModel):
    order_id: int
    user_id: str
    amount: float
    status: str

agent = Agent("DebugAgent")
channel = Channel()

@agent.typed_subscribe(Order)
async def handle_order(order: Order):
    print(f"Handler called with order: {order}")

async def main():
    eggai_set_default_transport(lambda: KafkaTransport())
    
    await agent.start()
    
    await channel.publish({
        "type": "OrderMessage",
        "source": "test-service", 
        "data": {
            "order_id": 123,
            "user_id": "user456",
            "amount": 99.99,
            "status": "requested"
        }
    })
    
    await asyncio.sleep(1)
    await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())