import os
import re
import json
import uuid
import httpx
import asyncpg
from mcp.server.fastmcp import FastMCP

# OpenTelemetry Imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# --- OpenTelemetry Initialization ---
resource = Resource(attributes={"service.name": "data-mcp-server"})
provider = TracerProvider(resource=resource)
otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint)))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("data-mcp-tracer")

# --- Server & Configuration ---
# Bind to 0.0.0.0:8080 if running in container (SSE), else defaults to standard
transport_mode = os.getenv("MCP_TRANSPORT", "stdio")
if transport_mode == "sse":
    mcp = FastMCP("Enterprise Data MCP", host="0.0.0.0", port=8080)
else:
    mcp = FastMCP("Enterprise Data MCP")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "localpassword123")
DB_NAME = os.getenv("DB_NAME", "ai_memory")
#OPA_URL = os.getenv("OPA_URL", "http://localhost:8181/v1/data/mcp/tools/allow")
# 'opa' forces Docker's internal DNS to route to the OPA container
OPA_URL = os.getenv("OPA_URL", "http://opa:8181/v1/data/mcp/tools/allow")

# Global singleton for connection pooling
_db_pool = None

async def get_db_pool():
    """Returns a singleton connection pool for the lifecycle of the server."""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            user=DB_USER, password=DB_PASS, database=DB_NAME, 
            host=DB_HOST, port=DB_PORT, min_size=1, max_size=10
        )
    return _db_pool

async def authorize_with_opa(tool_name: str, payload: dict) -> bool:
    """Queries the Open Policy Agent to determine if the tool execution is allowed."""
    try:
        req_json = {"input": {"tool": tool_name, **payload}}
        print(f"➡️ Sending to OPA at {OPA_URL}: {req_json}", flush=True)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OPA_URL, 
                json=req_json,
                timeout=2.0
            )
            print(f"⬅️ OPA Response: {response.text}", flush=True) # X-Ray: Inbound
            
            response.raise_for_status() 
            return response.json().get("result", False)
    except Exception as e:
        print(f"❌ OPA Connection/Evaluation Error: {e}", flush=True)
        return False

def is_valid_uuid(val: str) -> bool:
    """Strictly validates if a string is a UUID to prevent SQL injection in schema paths."""
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

@mcp.tool()
async def execute_read_query(query: str, session_id: str) -> str:
    """Executes a read-only SQL query against the agent's isolated workspace."""
    
    # 1. Start OpenTelemetry Trace
    with tracer.start_as_current_span("execute_read_query") as span:
        span.set_attribute("session_id", session_id)
        span.set_attribute("db.query", query)
        
        # 2. OPA Authorization Check
        is_authorized = await authorize_with_opa("execute_read_query", {"query": query, "session_id": session_id})
        span.set_attribute("opa.authorized", is_authorized)
        
        if not is_authorized:
            span.record_exception(Exception("OPA Policy Denied Execution"))
            return "ERROR: Unauthorized. Execution blocked by Open Policy Agent."

        # 3. SQL Injection Defense: UUID Validation for Schema Path
        if not is_valid_uuid(session_id):
            span.record_exception(Exception("Invalid session_id format"))
            return "ERROR: Invalid session_id format. Must be a valid UUID."

        # 4. Defense in Depth: Regex Fallback
        if not re.match(r"^\s*SELECT", query, re.IGNORECASE):
            span.record_exception(Exception("Mutating query attempted"))
            return "ERROR: Security Policy Violation. Only SELECT queries are permitted."

        schema_name = f"ws_{session_id.replace('-', '_')}"
        pool = await get_db_pool()
        
        try:
            async with pool.acquire() as conn:
                # 5. Enforce Read-Only at the database driver transaction level
                async with conn.transaction(readonly=True):
                    await conn.execute(f'SET search_path TO {schema_name}, public')
                    records = await conn.fetch(query)
                    
                    span.set_attribute("db.row_count", len(records))
                    
                    if not records:
                        return "Query executed successfully. No records found."
                        
                    results = [dict(record) for record in records]
                    output = json.dumps(results, default=str)
                    
                    # Truncate massive results to protect LLM context windows
                    if len(output) > 15000:
                        span.set_attribute("db.truncated", True)
                        return output[:15000] + "\n... [RESULTS TRUNCATED]"
                        
                    return output
                    
        except asyncpg.PostgresError as e:
            error_msg = f"DATABASE ERROR: {str(e)}"
            span.record_exception(e)
            return error_msg

if __name__ == "__main__":
    if transport_mode == "sse":
        print("Starting Enterprise Data MCP Server on SSE (Port 8080)...", flush=True)
        mcp.run(transport='sse')
    else:
        mcp.run(transport='stdio')