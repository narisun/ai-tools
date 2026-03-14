import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    # The URL where your Dockerized Data MCP server is listening for SSE connections
    url = "http://localhost:8080/sse"
    print(f"Connecting to MCP server at {url}...")
    
    # Establish the Server-Sent Events connection
    async with sse_client(url) as streams:
        # Create a session using the read and write streams
        async with ClientSession(streams[0], streams[1]) as session:
            # Initialize the connection handshake
            await session.initialize()
            print("✅ Connected to Enterprise Data MCP!\n")
            
            # --- TEST 1: The "Happy Path" (Valid Query & Valid UUID) ---
            print("--- Test 1: Authorized Read Query ---")
            try:
                result = await session.call_tool(
                    "execute_read_query", 
                    arguments={
                        "query": "SELECT 1 as system_check;", 
                        "session_id": "123e4567-e89b-12d3-a456-426614174000" # Valid UUID format
                    }
                )
                print(f"Response: {result.content[0].text}\n")
            except Exception as e:
                print(f"Error: {e}\n")

            # --- TEST 2: The "Hacker Path" (Mutating Query) ---
            print("--- Test 2: OPA Blocked Query (SQL Injection Attempt) ---")
            try:
                result = await session.call_tool(
                    "execute_read_query", 
                    arguments={
                        "query": "DROP TABLE accounts;", 
                        "session_id": "123e4567-e89b-12d3-a456-426614174000"
                    }
                )
                print(f"Response: {result.content[0].text}\n")
            except Exception as e:
                print(f"Error: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())