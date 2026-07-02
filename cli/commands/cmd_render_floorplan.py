import httpx
import json

def execute_render_floorplan(target_prompt: str) -> None:
    print(f"\n[CLI_RENDERER] Transmitting execution stream parameter to system pipeline matrix hook...")
    try:
        response = httpx.post("https://buildwise-aether-backend.onrender.com", json={"prompt": target_prompt}, timeout=20.0)
        if response.status_code != 200:
            print(f"[CLI_ERROR] Core service layer returned structural exception error flag: {response.status_code}")
            return
            
        payload = response.json()
        layout_rooms = payload.get("layout", [])
        
        print("\n" + "="*50 + "\n   ASCII ARCHITECTURAL SCHEMATIC VECTOR BOUNDS MAP\n" + "="*50)
        grid = [[" " for _ in range(50)] for _ in range(25)]
        
        for r in layout_rooms:
            x1, y1 = max(0, min(r["x1"], 49)), max(0, min(r["y1"] // 2, 24))
            x2, y2 = max(0, min(r["x2"], 49)), max(0, min(r["y2"] // 2, 24))
            
            for x in range(x1, x2):
                grid[y1][x] = "-"
                grid[y2][x] = "-"
            for y in range(y1, y2 + 1):
                grid[y][x1] = "|"
                grid[y][x2] = "|"
            
            # Anchor dynamic character string label markers inside structural geometric blocks
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            label = r["room_name"][:abs(x2-x1)-2]
            for char_idx, char in enumerate(label):
                if 0 <= mid_x + char_idx < 49:
                    grid[mid_y][mid_x + char_idx] = char

        for row in grid:
            print("".join(row))
        print("="*50)
        print(f"AUDIT SCORE: {payload.get('evaluation', {}).get('score')}% COMPLIANT")
        print(f"STRATEGY INJECTION VALUE: {payload.get('execution_context', {}).get('generation_strategy')}\n")
        
    except Exception as e:
        print(f"[CLI_FATAL] Network routing dropped or target core platform host offline: {str(e)}")