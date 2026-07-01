import asyncio
from backend.app.agents.requirements_agent import RequirementsAgent
from backend.app.agents.layout_agent import LayoutAgent
from backend.app.schemas.agent_msg import AgentMessage

def execute_agent_test(agent_name: str, target_prompt: str) -> None:
    print(f"\n[CLI_DIAGNOSTIC] Initializing isolated run sequence target node: '{agent_name}'")
    print(f"[CLI_DIAGNOSTIC] Input Param Parameters: \"{target_prompt}\"\n" + "-"*70)
    
    async def run():
        ctx = {"session_id": "cli_diagnostic_run_block", "prompt": target_prompt}
        if agent_name == "requirements":
            node = RequirementsAgent()
            res = await node.execute(ctx, [])
            print(f"SENDER SCOPE : {res.sender_id}")
            print(f"METADATA STATUS: {res.metadata.get('status')}")
            print(f"EXTRACTED PAYLOAD CONTENT:\n{res.content}")
        elif agent_name == "layout":
            node = LayoutAgent()
            # Feed pre-requisite mock requirements context message frame
            mock_req = AgentMessage(
                sender_id="RequirementsAgent",
                content="{\"target_rooms\": [{\"name\": \"Living\", \"min_area_sqft\": 200}]}"
            )
            res = await node.execute(ctx, [mock_req])
            print(f"SENDER SCOPE : {res.sender_id}")
            print(f"SYNTHESIZED MATRIX BLOCKS:\n{res.content}")
            
    asyncio.run(run())
    print("-"*70 + "\n[CLI_DIAGNOSTIC] Node execution sequence closed cleanly.")