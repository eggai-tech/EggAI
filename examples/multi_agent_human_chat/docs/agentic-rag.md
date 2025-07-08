# Agentic RAG – Introduction into RAG

## What is RAG?

Retrieval-Augmented Generation (RAG) combines traditional information retrieval with large language models (LLMs). Instead of generating answers purely from internal training data, RAG fetches relevant external documents at runtime and provides them as context to the model. This leads to more accurate, up-to-date, and verifiable responses.

## RAG vs. Agentic RAG

While RAG is typically a single-step query + generate process, **Agentic RAG** introduces reasoning and control by breaking the process into multiple steps, handled by autonomous agents. These agents can:

- Analyze user intent  
- Decompose complex questions  
- Fetch documents iteratively  
- Verify retrieved facts  
- Generate responses in stages  

Agentic RAG enables **multi-step reasoning**, **tool use**, and **task coordination**, turning simple retrieval into an active decision-making process.

## Key Concepts

- **Tokenization**: The process of splitting text into smaller units (tokens) that the model can understand. Tokens can be words, parts of words, or punctuation. LLMs have token limits that affect how much context they can process.

- **Embedding**: A vector representation of text used to compare semantic similarity. RAG systems use embeddings to find relevant content.

- **Context Window**: The maximum number of tokens a model can handle in a single request. Retrieved content must fit within this limit.

- **Chunking**: Breaking long documents into smaller pieces to make them retrievable and fit within the model’s context window.

- **Vector Store**: A database optimized for similarity search using embeddings.

## How It Works

1. **User Query**  
   A user asks a question or submits input.

2. **Embedding & Retrieval**  
   The system generates an embedding of the query and retrieves semantically similar chunks from a vector store.

3. **Prompt Construction**  
   Retrieved chunks are added to the prompt along with the original question.

4. **Generation**  
   The language model uses the combined context to generate a grounded response.

**In Agentic RAG**:  
Agents may iterate through this loop, ask follow-up questions, or call tools before generating a final output.
