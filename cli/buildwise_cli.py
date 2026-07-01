import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.agents.base_agent import orchestrator

def run_cli_diagnostic():
    print("=== BUILDWISE AETHER ENGINE DIAGNOSTIC ===")
    prompt = "Minimalist 3BHK setup with a pooja room"
    
    print(f"Analyzing prompt: '{prompt}'")
    options = orchestrator.construct_options(prompt, 45.0, 65.0, "rectangle", 2)
    
    for opt_id, payload in options.items():
        print(f"\nVariant Option Checked: {payload['display_name']}")
        print(f" -> Vastu Score: {payload['vastu_score']}/100")
        print(f" -> Style Track: {payload['style_applied']}")
        for fl in payload['floors']:
            print(f"    * Layer: {fl.floor_name} (Total Spaces Allocated: {len(fl.rooms)})")

if __name__ == "__main__":
    run_cli_diagnostic()