import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI



from src.graph.tools import search_semantic_timeline, fetch_biometric_metrics

# Maintain your existing tools array
health_tools = [search_semantic_timeline, fetch_biometric_metrics]

# Initialize your core reasoning model
llm = ChatOpenAI(model="gpt-4o", temperature=0)

system_prompt = """You are an advanced Health Twin Timeline Agent.
Your job is to help users analyze their health biometrics by coordinating semantic and time-series data.

When a user asks about an event or trend:
1. First, call the 'search_semantic_timeline' tool to find the exact event and timestamp of what they did.
2. Second, use the resulting timestamp to call 'fetch_biometric_metrics' to get the raw numbers right after that event.
3. Finally, synthesize a clear explanation correlating their habits (text data) with their biology (numbers).
Be precise, objective, and reference the exact timestamps found in memory.
"""

# 2. FIX: Re-compile your agent graph engine using the modern V1 API layout
health_twin_agent = create_agent(
    model=llm,
    tools=health_tools,
    system_prompt=system_prompt
)