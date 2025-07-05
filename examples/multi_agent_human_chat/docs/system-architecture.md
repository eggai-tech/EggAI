# System Architecture

## High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface"
        UI[Web Chat UI<br/>:8000]
    end
    
    subgraph "Message Broker"
        WS[WebSocket Gateway<br/>Frontend Agent]
        HC[Human Channel]
        AC[Agents Channel]
        AL[Audit Logs Channel]
    end
    
    subgraph "Core Agents"
        TR[Triage Agent<br/>Routes Messages]
        AU[Audit Agent<br/>Logs Everything]
    end
    
    subgraph "Specialized Agents"
        BI[Billing Agent<br/>Payment Info]
        CL[Claims Agent<br/>Claims Status]
        PO[Policies Agent<br/>RAG Search]
        ES[Escalation Agent<br/>Complex Issues]
    end
    
    subgraph "Infrastructure Services"
        RP[Redpanda<br/>:19092]
        VE[Vespa<br/>:8080/:19071]
        TE[Temporal<br/>:7233/:8081]
        ML[MLflow<br/>:5001]
        DB[(PostgreSQL<br/>:5432/:5433)]
    end
    
    subgraph "Monitoring"
        GR[Grafana<br/>:3000]
        PR[Prometheus<br/>:9090]
        OT[OTEL Collector<br/>:4318]
    end
    
    UI -.->|WebSocket| WS
    WS -->|Publish| HC
    HC -->|Subscribe| TR
    HC -->|Subscribe| AU
    TR -->|Route| AC
    AC -->|Subscribe| BI
    AC -->|Subscribe| CL
    AC -->|Subscribe| PO
    AC -->|Subscribe| ES
    
    AU -->|Log| AL
    
    PO -.->|Search| VE
    PO -.->|Workflows| TE
    
    HC -.->|Messages| RP
    AC -.->|Messages| RP
    AL -.->|Messages| RP
    
    TE -.->|State| DB
    ML -.->|Metadata| DB
    
    OT -->|Metrics| PR
    PR -->|Display| GR

    style UI fill:#e1f5fe
    style WS fill:#fff3e0
    style TR fill:#f3e5f5
    style AU fill:#f3e5f5
    style BI fill:#e8f5e9
    style CL fill:#e8f5e9
    style PO fill:#e8f5e9
    style ES fill:#e8f5e9
```

## Component Responsibilities

### Message Flow Components

**Frontend Agent (WebSocket Gateway)**
- Manages WebSocket connections
- Handles reconnections and buffering
- Publishes to Human Channel

**Human Channel**
- Primary channel for user messages
- Subscribed by Triage and Audit agents
- Carries user requests and agent responses

**Agents Channel**
- Secondary channel for routed messages
- Subscribed by specialized agents
- Carries messages after triage routing

### Agent Components

**Triage Agent**
- Classifies user intent using ML models (v0-v5)
- Routes to appropriate specialized agent
- Handles small talk directly

**Specialized Agents**
- **Billing**: Payment info, premiums, due dates
- **Claims**: Claim status, filing, updates
- **Policies**: RAG-based document search
- **Escalation**: Complex issues, complaints

**Audit Agent**
- Monitors all channels
- Creates structured audit logs
- Provides compliance trail

### Infrastructure Services

**Redpanda (Kafka-compatible)**
- Message broker for all channels
- Ensures reliable message delivery
- Provides topic management

**Vespa**
- Vector search engine
- Stores policy documents
- Powers RAG for Policies agent

**Temporal**
- Workflow orchestration
- Manages document ingestion
- Provides durability and retries

## Message Routing Logic

```mermaid
graph LR
    subgraph "Triage Decision Tree"
        Q[User Query] --> A{Analyze Intent}
        
        A -->|Payment/Premium| B[Route to Billing]
        A -->|Claim Related| C[Route to Claims]
        A -->|Policy Info| D[Route to Policies]
        A -->|Complaint/Complex| E[Route to Escalation]
        A -->|Greeting/Chat| F[Handle Directly]
        
        B --> AC1[Agents Channel]
        C --> AC2[Agents Channel]
        D --> AC3[Agents Channel]
        E --> AC4[Agents Channel]
        F --> HC[Human Channel]
    end
```

## Data Flow Patterns

### 1. Synchronous Request-Response
```
User → Frontend → Human Channel → Triage → Agent → Response
```

### 2. Asynchronous Processing
```
Documents → Temporal Workflow → Vespa Index
User Query → Policies Agent → Vespa Search → Response
```

### 3. Audit Trail
```
All Messages → Audit Agent → Audit Logs Channel → Storage
```

## Scalability Considerations

- **Horizontal Scaling**: Each agent can run multiple instances
- **Channel Partitioning**: Redpanda supports partitioned topics
- **Stateless Agents**: No shared state between agent instances
- **Distributed Search**: Vespa cluster with 3 nodes

## Security Boundaries

- **WebSocket Gateway**: Input validation and rate limiting
- **Agent Isolation**: Each agent runs in separate process
- **Channel Security**: Message encryption in transit
- **Audit Compliance**: Complete message history

## Communication Flow Example

This sequence diagram shows a typical interaction where a user asks about their insurance policy:

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant HumanChannel
    participant Triage
    participant AgentsChannel
    participant Policies
    participant Audit

    User->>Frontend: Send greeting (e.g., "hi")
    Frontend->>HumanChannel: Forward user input
    HumanChannel->>+Audit: Log message
    HumanChannel->>Triage: Forward to Triage
    Triage-->>HumanChannel: Respond with initial greeting (e.g., "Hello! How can I assist?")
    HumanChannel->>+Audit: Log message
    HumanChannel-->>Frontend: Send response
    Frontend-->>User: Display response

    User->>Frontend: Ask for help with insurance (e.g., "I want to know what's included in my policy")
    Frontend->>HumanChannel: Forward user input
    HumanChannel->>+Audit: Log message
    HumanChannel->>Triage: Forward to Triage
    Triage->>AgentsChannel: Forward to Policies
    AgentsChannel->>+Audit: Log message
    AgentsChannel->>Policies: Forward to Policies
    Policies-->>HumanChannel: Ask for clarification (e.g., "Can you provide your policy number?")
    HumanChannel->>+Audit: Log message
    HumanChannel-->>Frontend: Send response
    Frontend-->>User: Display response

    User->>Frontend: Provide policy number (e.g., A12345)
    Frontend->>HumanChannel: Forward user input
    HumanChannel->>+Audit: Log message
    HumanChannel->>Triage: Forward to Triage
    Triage->>AgentsChannel: Forward to Policies
    AgentsChannel->>+Audit: Log message
    AgentsChannel->>Policies: Forward to Policies
    Policies-->>HumanChannel: Return policy details (e.g., "Your insurance with the policy number A12345 includes...")
    HumanChannel->>+Audit: Log message
    HumanChannel-->>Frontend: Send response
    Frontend-->>User: Display response
```