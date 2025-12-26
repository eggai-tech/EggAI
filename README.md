<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/eggai-word-and-figuremark.svg" alt="EggAI" width="200px" />

# Multi-Agent Meta Framework

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/eggai)](https://pypi.org/project/eggai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](https://opensource.org/licenses/MIT)

<!--start-->

Build multi-agent systems with an async-first, distributed architecture. Framework-agnostic, works with DSPy, LangChain, LlamaIndex, and more.

## Install

```bash
pip install eggai
```

## Quick Example

```python
import asyncio
from eggai import Agent, Channel

agent = Agent("MyAgent")
channel = Channel()

@agent.subscribe(filter_by_message=lambda e: e.get("type") == "greet")
async def handle(event):
    print(f"Received: {event}")

async def main():
    await agent.start()
    await channel.publish({"type": "greet", "message": "Hello!"})
    await asyncio.sleep(1)

asyncio.run(main())
```

## Resources

- **[Documentation](https://docs.egg-ai.com/)** - Full SDK reference and guides
- **[Examples](https://github.com/eggai-tech/eggai-examples)** - Integration examples (DSPy, LangChain, LiteLLM, etc.)
- **[Demo](https://github.com/eggai-tech/eggai-demo)** - Multi-agent insurance support system

## Transports

| Transport | Use Case |
|-----------|----------|
| InMemory | Testing, prototyping |
| Redis Streams | Production (recommended) |
| Kafka | High-throughput production |

<!--end-->

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT - see [LICENSE.md](LICENSE.md)
