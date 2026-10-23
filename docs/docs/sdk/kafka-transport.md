# KafkaTransport

Kafka support is the `kafka` extra, which installs FastStream and aiokafka:

```bash
pip install "eggai[kafka]"
```

Without it, importing `KafkaTransport` raises an `ImportError` that names the extra.

::: eggai.transport.KafkaTransport