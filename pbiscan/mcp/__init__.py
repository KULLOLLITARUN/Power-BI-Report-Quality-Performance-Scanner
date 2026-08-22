"""PBIP Sentinel Model Context Protocol (MCP) Server.

Exposes deterministic static analysis, rule catalog resources, safe remediation planning,
and host-assisted DAX advisory rewrites over standard stdio JSON-RPC.
"""
from __future__ import annotations

__all__ = ["create_mcp_server", "run_mcp_server"]


def create_mcp_server():
    """Factory creating and configuring the PBIP Sentinel FastMCP server instance."""
    from pbiscan.mcp.server import create_server
    return create_server()


def run_mcp_server() -> None:
    """Run the PBIP Sentinel MCP server over stdio transport."""
    server = create_mcp_server()
    server.run(transport="stdio")
