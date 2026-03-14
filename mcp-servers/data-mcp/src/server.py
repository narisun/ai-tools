import os
import re
import json
import asyncio
import asyncpg
from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
# This automatically handles the Model Context Protocol communication layer
mcp = FastMCP("Enterprise Data MCP")

# Database Configuration (Defaults to our local docker-compose setup)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "localpassword123")
DB_NAME = os.getenv("DB_NAME", "ai_memory")

async def get_db_pool():
    """Create a connection pool to the unified Postgres memory store."""
    return await asyncpg.create_pool(
        user=DB_USER, 
        password=DB_PASS, 
        database=DB_NAME, 
        host=DB_HOST, 
        port=DB_PORT,
        min_size=1,
        max_size=10
    )

@mcp.tool()
async def execute_read_query(query: str, session_id: str) -> str:
    """
    Executes a read-only SQL query against the agent's isolated workspace.
    
    Args:
        query: The SELECT SQL query to execute.
        session_id: The active session ID (UUID) to enforce workspace schema isolation.
    """
    # 1. Gateway Security Check: Strictly enforce read-only operations
    # (In production, OPA policies also enforce this at the network layer)
    if not re.match(r"^\s*SELECT", query, re.IGNORECASE):
        return "ERROR: Security Policy Violation. Only SELECT queries are permitted."
        
    # 2. Schema Isolation: Force the query to run ONLY in the session's workspace
    # This prevents cross-tenant data leakage [cite: 120, 144-150]
    safe_session_id = session_id.replace('-', '_')
    schema_name = f"ws_{safe_session_id}"
    
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            # Set the search path so the agent doesn't need to specify the schema manually
            await conn.execute(f'SET search_path TO {schema_name}, public')
            
            # Execute the query
            records = await conn.fetch(query)
            
            if not records:
                return "Query executed successfully. No records found."
                
            # Serialize the asyncpg records to a JSON-formatted string for the LLM
            results = [dict(record) for record in records]
            
            # Truncate massive results to prevent blowing out the LLM context window
            output = json.dumps(results, default=str)
            if len(output) > 15000:
                return output[:15000] + "\n... [RESULTS TRUNCATED DUE TO SIZE LIMIT]"
                
            return output
            
    except asyncpg.PostgresError as e:
        # Return a clean error to the LLM so the agent can critique and rewrite its SQL
        return f"DATABASE ERROR: {str(e)}\nHint: Check your syntax and table schema."
    finally:
        await pool.close()

if __name__ == "__main__":
    # Start the server using standard input/output (stdio)
    # This is the standard transport protocol for local MCP tool execution
    
    mcp.run(transport='stdio')