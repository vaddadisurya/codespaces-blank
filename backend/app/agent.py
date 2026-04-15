import json
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.prebuilt import create_react_agent
from app.config import NVIDIA_API_KEY, LLM_MODEL
from app.tools import query_sensor_data, get_trend_analysis, get_energy_rates
from app.rag import search_knowledge

# 1. Initialize NVIDIA LLM
llm = ChatNVIDIA(model=LLM_MODEL, api_key=NVIDIA_API_KEY, temperature=0.1)

# 2. Bind LangChain Tools
tools = [query_sensor_data, get_trend_analysis, get_energy_rates, search_knowledge]

# 3. Strict System Prompt
SYSTEM_PROMPT = """
You are the Building 59 Facilities Management AI Assistant. 
You ONLY answer questions about Building 59 sensor data, equipment health, energy, and compliance. 

RULES:
- WHAT-IF SCENARIOS: If asked "what happens if X changes", use physics formulas (Efficiency = airflow/speed, Delta-T = return-supply) to calculate cascading effects. 
- PREDICTIONS: Use get_trend_analysis to find the daily rate of change and extrapolate.
- COSTS: Use get_energy_rates and multiply total_kw * hours * rate.
- CONSTRAINTS: Be concise. Show calculations. If asked about general topics outside Building 59, politely decline.
"""

# 4. Create the LangGraph Agent Orchestrator
# BUGFIX: We pass NO modifier kwargs here to prevent TypeError crashes across different versions.
agent_executor = create_react_agent(llm, tools)

async def process_chat(user_message: str, history: list) -> str:
    """Processes a user message through the LangGraph React loop."""
    
    # Manually inject the system prompt at the very beginning of the conversation
    messages = [("system", SYSTEM_PROMPT)]
    
    # Add previous history
    for msg in history:
        messages.append((msg["role"], msg["content"]))
        
    # Add current user message
    messages.append(("user", user_message))
    
    # Run the agent
    result = await agent_executor.ainvoke({"messages": messages})
    
    # Return the final message content from the agent
    return result["messages"][-1].content

def run_autonomous_check() -> list:
    """Runs a scheduled check. The agent autonomously uses tools to get real data."""
    prompt = """
    Use your tools to check the current status and trends for:
    1. Pump vibration (pump_vibration_mms)
    2. Hot water temperature (hw_temp_celsius)
    
    CRITICAL RULE: You must only call ONE tool at a time. Call the tool for vibration, wait for the result, then call the tool for hot water. Do NOT output multiple tool calls at once.
    
    Compare these against known thresholds (vibration critical > 7.0, hw legionella < 60.0).
    
    Output ONLY a valid JSON array. Each item must have:
    - "severity": "critical", "warning", or "info"
    - "system": e.g., "Pumps" or "Compliance"
    - "summary": A one-sentence summary.
    - "detail": 2-3 sentences with exact numbers and a recommended action.
    """
    
    # Inject the system prompt and the task
    messages = [
        ("system", SYSTEM_PROMPT),
        ("user", prompt)
    ]
    
    try:
        result = agent_executor.invoke({"messages": messages})
        text = result["messages"][-1].content.strip()
        
        # Clean up markdown JSON code blocks if the LLM generates them
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
            
        return json.loads(text)
    except Exception as e:
        print(f"Failed to parse agent JSON or run check: {e}")
        return []