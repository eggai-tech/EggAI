# Example Flow

**User**

The user comes up with some message.

> "Hello, does my insurance cover car damages?"

This message is passed from the browser to the webserver via Websocket.  
The webserver publishes this message to the kafka topic `human_channel`.

**Triage Agent**

The triage agent has a subscription on the kafka topic `human_channel`. Because of this, he receives the message from the user.

This incoming message is added to the chat history. Based on the chat history, especially on the most recent message, the triage agent decides, whats the best way to process the users message and how to respond.

In general, there are 2 main outcomes:

1. Sending a direct response, which is sufficient for greetings and similar small talk. Here the agent passes the response to the `human_channel`.
2. Deligating the request to a specialized agent by publishing a kafka message to `agents_channel`.

The evaluation on how to process the received message is done by doing a classification. Here, the chat message/recent chat history is classified into predefined types.

This means, the triage agent is decoupled from other agents:

- the triage agent itself, does not have knowledge about other agents itself
- the triage agent only knows the possible types (classification) for messages

In this example the kafka message type will be set to `policy_request`.

**Policies Agent**

The policies agent is subscribed to the `agents_channel`. When a message receives with a relevant message type set, the agent starts processing.

The response is than passed to the `human_channel`.

**User**

As the webserver has a subscription to the `human_channel`, he is able to receive chat conversation related messages, and pass them via Websocket to the users browser, where the response gets displayed.
