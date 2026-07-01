import subprocess
import json
import os
from typing import Dict, Any

class MCPClient:
    """
    Handles standard Model Context Protocol (MCP) process loops 
    to retrieve verified context records from sub-servers.
    """
    def __init__(self):
        self.server_registry = {
            "building_codes": os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp_servers", "server_building_codes.py"),
            "cad_templates": os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp_servers", "server_cad_templates.py")
        }

    def call_tool(self, target_server: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        script_path = self.server_registry.get(target_server)
        if not script_path or not os.path.exists(script_path):
            raise FileNotFoundError(f"MCP subserver target path missing: {target_server}")

        # Spawn sub-process using absolute isolated pipeline execution pipes
        proc = subprocess.Popen(
            ["python", script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # 1. Dispatch Protocol handshake init message block
        init_cmd = json.dumps({"id": 1, "method": "initialize", "params": {}}) + "\n"
        proc.stdin.write(init_cmd)
        proc.stdin.flush()
        proc.stdout.readline()

        # 2. Transmit the target tools execution command payload
        exec_payload = {
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        proc.stdin.write(json.dumps(exec_payload) + "\n")
        proc.stdin.flush()

        raw_response = proc.stdout.readline()
        
        # Shutdown transaction pipeline interfaces cleanly
        proc.stdin.close()
        proc.terminate()

        parsed = json.loads(raw_response)
        content_block = parsed.get("result", {}).get("content", [{}])[0]
        return content_block.get("text", "{}")