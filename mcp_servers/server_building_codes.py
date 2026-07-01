#!/usr/bin/env python3
import sys
import json
import os
from typing import Dict, Any, List

def write_mcp_response(response: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()

def main():
    # RFC 4122 Standard MCP Protocol Loop over Standard I/O Channels
    irc_data_path = os.path.join(
        os.path.dirname(__file__), 
        "..", "data", "standard_codes", "residential_irc.json"
    )
    
    # Initialize static legal rules fallback database if physical path misses
    building_codes = {
        "residential": {
            "min_room_dimension_ft": 7.0,
            "min_ceiling_height_ft": 7.0,
            "egress_window_min_width_in": 20.0,
            "egress_window_min_height_in": 24.0,
            "hallway_min_width_ft": 3.0,
            "bathroom_clearance_front_in": 21.0
        }
    }
    
    if os.path.exists(irc_data_path):
        try:
            with open(irc_data_path, "r") as f:
                building_codes = json.load(f)
        except Exception:
            pass

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
                
            request = json.loads(line)
            req_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})

            if method == "initialize":
                write_mcp_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {
                                "listChanged": False
                            }
                        },
                        "serverInfo": {
                            "name": "BuildWise IRC Code Server",
                            "version": "1.0.0"
                        }
                    }
                })
            elif method == "tools/list":
                write_mcp_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "validate_clearance_limits",
                                "description": "Validates if architectural room spans fulfill minimum IRC International Residential Code constraints.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "room_type": {"type": "string"},
                                        "width_ft": {"type": "number"},
                                        "height_ft": {"type": "number"}
                                    },
                                    "required": ["room_type", "width_ft", "height_ft"]
                                }
                            }
                        ]
                    }
                })
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name == "validate_clearance_limits":
                    r_type = arguments.get("room_type", "generic")
                    w = arguments.get("width_ft", 0.0)
                    h = arguments.get("height_ft", 0.0)
                    
                    min_dim = building_codes.get("residential", {}).get("min_room_dimension_ft", 7.0)
                    is_valid = (w >= min_dim) and (h >= min_dim)
                    area = w * h
                    
                    write_mcp_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps({
                                        "compliant": is_valid,
                                        "evaluated_dimensions": f"{w}x{h}",
                                        "minimum_allowed_dimension": min_dim,
                                        "total_area_sqft": area,
                                        "code_reference": "IRC 2026 Section R304.1"
                                    })
                                }
                            ]
                        }
                    })
            else:
                write_mcp_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": "Method not found"}
                })
        except Exception as e:
            write_mcp_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)}
            })

if __name__ == "__main__":
    main()