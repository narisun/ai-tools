package mcp.tools

import rego.v1

default allow := false

allow if {
    input.tool == "execute_read_query"
    input.session_id != ""
    # Use backticks for raw strings to prevent escape-character bugs
    regex.match(`(?i)^\s*SELECT`, input.query)
}