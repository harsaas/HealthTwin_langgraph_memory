import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv


# Ensure imports work when running: `streamlit run streamlit_app.py`
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load env first (DATABASE_URL, OPENAI_API_KEY, etc.)
load_dotenv(dotenv_path=REPO_ROOT / ".env", override=True)

# Demo default: align semantic timeline with biometrics.
# Override in shell or .env if you want the original table.
os.environ.setdefault("SEMANTIC_TABLE_NAME", "semantic_timeline_food_demo")

from src.graph.workflow import health_twin_agent  # noqa: E402


def _render_message(role: str, content: str) -> None:
    with st.chat_message(role):
        st.markdown(content)


st.set_page_config(page_title="HealthTwin", layout="centered")
st.title("HealthTwin")

if "messages" not in st.session_state:
    st.session_state.messages = []  # list[dict]

# Render prior chat
for msg in st.session_state.messages:
    role = msg.get("role", "assistant")
    content = msg.get("content", "")
    _render_message(role, content)

prompt = st.chat_input("Ask about your biometrics and meals...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    _render_message("user", prompt)

    with st.chat_message("assistant"):
        status = st.status("Running agent...", expanded=False)
        output_box = st.empty()
        tool_box = st.empty()

        final_messages = None
        try:
            # Pass full chat history (as role/content dicts)
            agent_input = {"messages": st.session_state.messages}

            for chunk in health_twin_agent.stream(agent_input, stream_mode="values"):
                final_messages = chunk.get("messages")
                if not final_messages:
                    continue

                latest = final_messages[-1]

                # LangChain messages have .type, .content; tool messages may have .name
                msg_type = getattr(latest, "type", None)
                msg_content = getattr(latest, "content", "")

                if msg_type in {"ai", "assistant"}:
                    output_box.markdown(msg_content or "")
                elif msg_type in {"tool"}:
                    tool_name = getattr(latest, "name", "tool")
                    tool_box.markdown(f"**Tool:** {tool_name}\n\n{msg_content}")
                else:
                    # human/system/unknown — ignore incremental rendering
                    pass

            status.update(label="Done", state="complete")

        except Exception as e:
            status.update(label="Error", state="error")
            st.exception(e)

    # Persist the assistant final message back into session_state
    # (We only store user+assistant text, not tool messages, to keep it simple.)
    if final_messages:
        for m in reversed(final_messages):
            m_type = getattr(m, "type", None)
            if m_type in {"ai", "assistant"}:
                assistant_text = getattr(m, "content", "")
                st.session_state.messages.append({"role": "assistant", "content": assistant_text})
                break
