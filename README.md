# Enterprise Agent Capabilities (`ai-tools`)

This repository contains the independent, containerized capabilities that our LangGraph agents invoke to interact with the outside world. [cite_start]All tools are exposed via the **Model Context Protocol (MCP)** to ensure standardized, cross-framework interoperability [cite: 11-12, 51-56].

## 🏗 Core Architecture

In a highly regulated environment, agents cannot have unconstrained access to data. This repository implements a zero-trust execution model:
1. **Universal Interface:** Tools are built as isolated MCP servers (e.g., `data-mcp` for SQL, `api-mcp` for internal banking APIs).
2. **Policy as Code (OPA):** Every tool invocation is gated by the Open Policy Agent (OPA). [cite_start]The Rego policies in `policies/opa/` evaluate the agent's identity, the requested tool, and the payload before execution is permitted [cite: 174-175, 189-190].
3. [cite_start]**Traceability:** All MCP servers must be instrumented with OpenTelemetry to link tool execution latency and status back to the agent's decision trace in Dynatrace [cite: 209-214].

## 📂 Repository Structure

* `/mcp-servers/`: Contains the individual tool microservices.
  * `data-mcp`: Enables agents to query authorized database schemas securely.
  * `search-mcp`: Enables vector semantic search against our pgvector knowledge base.
  * `api-mcp`: Enables interaction with internal banking REST/gRPC endpoints.
* `/policies/`: Contains OPA Rego policies enforcing least-privilege tool execution.
* `/local-dev/`: Docker Compose configurations for testing tools locally before deployment.

## 💻 Local Development Environment

To test an MCP server locally, you can use the official MCP Inspector or write a simple Python client.

1. **Navigate to the target MCP server:**
    ```bash
    cd mcp-servers/data-mcp
    ```

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Run the server locally:**
    ```bash
    python src/server.py
    ```



*Note: MCP servers communicate over standard input/output (stdio) or Server-Sent Events (SSE). For local testing, we rely on `stdio`.*

## 🔐 Security & Governance

Before deploying any new MCP server or tool, ensure:

* The tool has a corresponding explicit **ALLOW** rule in `policies/opa/tool_auth.rego`.
* It does not log sensitive PII/financial data in its OpenTelemetry traces.
* Database tools only execute against the isolated `ws_{session_id}` workspace schemas, adhering to Row-Level Security (RLS) policies .
## Folder Structure

```
ai-tools/
├── mcp-servers/
│   ├── data-mcp/                # Secure database querying (PostgreSQL/pgvector)
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── server.py        # The MCP server definition and tool registration
│   │   │   └── database.py      # Connection pooling and query execution
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── search-mcp/              # Semantic search and RAG capabilities
│   └── api-mcp/                 # Internal REST/gRPC banking API integration
├── policies/
│   └── opa/                     # Rego policies for tool-level authorization
│       └── tool_auth.rego       # Rules defining which agents can call which tools
├── local-dev/
│   └── docker-compose.yml       # Local testing stack for standing up MCP tools
└── README.md
```