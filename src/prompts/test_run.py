import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Allow running this file directly: `python src/prompts/test_run.py`
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

load_dotenv(dotenv_path=repo_root / ".env", override=True)

# Demo default: use the shifted semantic table so food logs align with biometrics.
# If you want the original table, set SEMANTIC_TABLE_NAME in your shell/.env.
os.environ.setdefault("SEMANTIC_TABLE_NAME", "semantic_timeline_food_demo")

from src.graph.workflow import health_twin_agent

def run_demo():
    print("Initializing Health Twin Agent Session...")
    
    user_input = {
        "messages": [
            {"role": "user", "content": "Can you check my glucose timeline? Why did I experience a massive blood sugar spike last Tuesday morning?"}
        ]
    }
    
    # Stream the graph execution to watch the tool-calling loop live
    for chunk in health_twin_agent.stream(user_input, stream_mode="values"):
        latest_message = chunk["messages"][-1]
        latest_message.pretty_print()

if __name__ == "__main__":
    run_demo()