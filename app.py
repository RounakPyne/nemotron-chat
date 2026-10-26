import json
import uuid
from datetime import datetime

import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="Nemotron",
    page_icon="✻",
    layout="wide",
    initial_sidebar_state="expanded",
)

# The API key is configured in Streamlit server secrets, never in the UI.
try:
    NVIDIA_API_KEY = st.secrets["NVIDIA_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("The server administrator must configure NVIDIA_API_KEY in Streamlit Secrets.")
    st.stop()

MODEL_ID = st.secrets.get("NVIDIA_MODEL_ID", "nvidia/nemotron-3-ultra-550b-a55b")

st.markdown("""
<style>
:root { --bg:#FAF9F5; --side:#F0EEE6; --text:#3D3929; --muted:#83827D; --accent:#C96442; --bubble:#EDEADF; --line:#E3E0D5; }
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background:var(--bg) !important; color:var(--text); }
[data-testid="stHeader"] { background:var(--bg) !important; }
#MainMenu, footer { visibility:hidden; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background:var(--side) !important; border-right:1px solid var(--line); }
[data-testid="stSidebar"] * { color:var(--text); }
[data-testid="stSidebarCollapsedControl"] { visibility:visible !important; display:flex !important; }
h1,h2,h3,.brand,.welcome { font-family:Georgia,"Times New Roman",serif !important; font-weight:400 !important; color:var(--text) !important; }
.brand { font-size:1.55rem; margin:0 0 .8rem .1rem; }
.brand span,.welcome span { color:var(--accent); }
.sec { font-size:.8rem; color:var(--muted); margin:.8rem 0 .3rem .2rem; }
.welcome { text-align:center; font-size:2.5rem; margin-top:15vh; line-height:1.3; }
.welcome span { margin-right:10px; }
.sub { text-align:center; color:var(--muted); }
[data-testid="stChatMessage"] { background:transparent; padding:.35rem 0; }
[data-testid="stChatMessageAvatarUser"],[data-testid="stChatMessageAvatarAssistant"] { display:none; }
[data-testid="stExpander"] { border:1px solid var(--line) !important; border-radius:12px; background:transparent; }
.stButton > button { border-radius:10px; border-color:transparent; color:var(--text); background:transparent; }
.stButton > button:hover { background:#E6E3D8; border-color:transparent; }
[data-testid="stSidebar"] input,[data-testid="stSidebar"] textarea { background:white !important; border-radius:10px; }
div[data-testid="stTextInput"] input { border-radius:14px; }
</style>
""", unsafe_allow_html=True)

S = st.session_state
S.setdefault("chats", {})
S.setdefault("projects", {"Personal": {"description": "General conversations"}})
S.setdefault("current", None)
S.setdefault("thinking", False)
S.setdefault("draft", "")

def new_chat():
    S.current = None
    S.draft = ""

def open_chat(cid):
    S.current = cid

def delete_chat(cid):
    S.chats.pop(cid, None)
    if S.current == cid:
        S.current = None

def toggle_pin(cid):
    S.chats[cid]["pinned"] = not S.chats[cid].get("pinned", False)

def create_project():
    name = S.get("new_project_name", "").strip()
    if name and name not in S.projects:
        S.projects[name] = {"description": S.get("new_project_description", "").strip()}
        S.new_project_name = ""
        S.new_project_description = ""

def render_chat_button(cid):
    c = S.chats[cid]
    title = c.get("title", "New chat")
    if len(title) > 24:
        title = title[:23] + "…"
    a, b, d = st.columns([6, 1, 1], gap="small")
    a.button(title, key=f"open_{cid}", on_click=open_chat, args=(cid,), use_container_width=True)
    b.button("★" if c.get("pinned") else "☆", key=f"pin_{cid}", on_click=toggle_pin, args=(cid,), help="Pin chat")
    d.button("×", key=f"delete_{cid}", on_click=delete_chat, args=(cid,), help="Delete chat")

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown('<div class="brand"><span>✻</span> Nemotron</div>', unsafe_allow_html=True)
    st.button("＋  New chat", on_click=new_chat, use_container_width=True)
    search = st.text_input("Search chats", placeholder="🔍  Search chats", label_visibility="collapsed", key="search").strip().lower()

    st.markdown('<div class="sec">Projects</div>', unsafe_allow_html=True)
    project_names = list(S.projects.keys())
    selected_project = st.selectbox("Filter by project", ["All projects"] + project_names, label_visibility="collapsed", key="project_filter")
    with st.expander("＋ Create project"):
        st.text_input("Project name", key="new_project_name", placeholder="e.g. Risk Analytics")
        st.text_input("Description (optional)", key="new_project_description", placeholder="What is this project for?")
        st.button("Create project", on_click=create_project, use_container_width=True)

    if project_names:
        for pname in project_names:
            project_chats = [cid for cid, c in S.chats.items() if c.get("project") == pname]
            with st.expander(f"📁 {pname} ({len(project_chats)})", expanded=(selected_project == pname)):
                for cid in reversed(project_chats):
                    if cid in S.chats and (not search or search in S.chats[cid].get("title", "").lower() or any(search in m.get("content", "").lower() for m in S.chats[cid].get("messages", []))):
                        render_chat_button(cid)

    st.markdown('<div class="sec">Recent chats</div>', unsafe_allow_html=True)
    chat_ids = list(reversed(list(S.chats.keys())))
    if selected_project != "All projects":
        chat_ids = [cid for cid in chat_ids if S.chats[cid].get("project") == selected_project]
    chat_ids = [cid for cid in chat_ids if not search or search in S.chats[cid].get("title", "").lower() or any(search in m.get("content", "").lower() for m in S.chats[cid].get("messages", []))]
    for cid in chat_ids:
        if selected_project == "All projects" and S.chats[cid].get("project"):
            continue
        render_chat_button(cid)
    chat = S.chats.get(S.current)
    messages = chat.get("messages", []) if chat else []
    if chat:
        project_name = chat.get("project") or "No project"
        chat_title = chat.get("title") or "New chat"
        st.caption(f"{project_name} · {chat_title}")


    with st.expander("Settings"):
        st.caption("The API key is configured securely by the site owner and is not shown here.")
        S.user_name = st.text_input("Your name", value=S.get("user_name", "Rounak"), key="display_name")
        S.system_prompt = st.text_area("System prompt", value=S.get("system_prompt", "You are a helpful assistant."), key="system_prompt_input")
        S.temperature = st.slider("Temperature", 0.0, 1.5, float(S.get("temperature", 0.7)), 0.05, key="temperature_slider")
        S.max_tokens = st.slider("Max response tokens", 256, 16384, int(S.get("max_tokens", 4096)), 256, key="max_tokens_slider")

    with st.expander("Save / load chats"):
        st.caption("Download a backup or import a previously exported JSON file.")
        st.download_button("Download chats", data=json.dumps({"chats": S.chats, "projects": S.projects}, ensure_ascii=False, indent=2), file_name="nemotron-backup.json", mime="application/json", use_container_width=True)
        uploaded = st.file_uploader("Import backup", type="json", key="backup_upload")
        if uploaded and S.get("import_signature") != (uploaded.name, uploaded.size):
            try:
                data = json.loads(uploaded.getvalue())
                if "chats" in data:
                    S.chats.update(data.get("chats", {}))
                    S.projects.update(data.get("projects", {}))
                else:
                    S.chats.update(data)
                S.import_signature = (uploaded.name, uploaded.size)
                st.rerun()
            except (ValueError, TypeError):
                st.error("Could not read that JSON backup.")

# ---------- Main panel ----------
chat = S.chats.get(S.current)
messages = chat.get("messages", []) if chat else []

if chat:
    st.caption(chat.get("project", "No project") + "  ·  " + chat.get("title", "New chat"))
if not messages:
    st.markdown(f'<div class="welcome"><span>✻</span> Hi, {S.get("user_name", "there")}</div>', unsafe_allow_html=True)
    st.markdown('<p class="sub">What would you like to explore today?</p>', unsafe_allow_html=True)

for m in messages:
    with st.chat_message(m.get("role", "assistant")):
        if m.get("reasoning"):
            with st.expander("Thinking"):
                st.markdown(m["reasoning"])
        st.markdown(m.get("content", ""))

# Composer: thinking toggle is beside the message field.
st.divider()
compose_col, thinking_col = st.columns([10, 2], vertical_alignment="bottom")
with compose_col:
    with st.form("message_form", clear_on_submit=True, border=False):
        prompt = st.text_area("Message Nemotron", placeholder="Message Nemotron…", label_visibility="collapsed", height=76, key="message_draft")
        send = st.form_submit_button("↑  Send", use_container_width=True)
with thinking_col:
    st.toggle("Thinking", key="thinking", help="Show the model's reasoning when supported by the model/API.")
    st.caption("Model: Nemotron")

if send and prompt.strip():
    if chat is None:
        cid = uuid.uuid4().hex[:10]
        title = prompt.strip().splitlines()[0][:40] or "New chat"
        default_project = selected_project if selected_project != "All projects" else None
        S.chats[cid] = {"title": title, "messages": [], "pinned": False, "project": default_project}
        S.current = cid
        chat = S.chats[cid]
        messages = chat["messages"]

    messages.append({"role": "user", "content": prompt.strip()})
    api_messages = [{"role": "system", "content": S.get("system_prompt", "You are a helpful assistant.")}]
    api_messages.extend({"role": m["role"], "content": m["content"]} for m in messages if m.get("role") in ("user", "assistant"))

    with st.chat_message("user"):
        st.markdown(prompt.strip())

    with st.chat_message("assistant"):
        try:
            client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=NVIDIA_API_KEY)
            stream = client.chat.completions.create(
                model=MODEL_ID,
                messages=api_messages,
                temperature=S.get("temperature", 0.7),
                top_p=0.95,
                max_tokens=S.get("max_tokens", 4096),
                extra_body={"chat_template_kwargs": {"enable_thinking": S.get("thinking", False)}},
                stream=True,
            )
            reasoning, reply = "", ""
            think_box = None
            if S.get("thinking", False):
                think_box = st.expander("Thinking", expanded=True)
                think_placeholder = think_box.empty()
            answer_placeholder = st.empty()
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                r = getattr(delta, "reasoning_content", None)
                if r and S.get("thinking", False):
                    reasoning += r
                    think_placeholder.markdown(reasoning)
                if delta.content:
                    reply += delta.content
                    answer_placeholder.markdown(reply + "▌")
            answer_placeholder.markdown(reply or "The model returned an empty response.")
            messages.append({"role": "assistant", "content": reply, "reasoning": reasoning})
            st.rerun()
        except Exception as exc:
            st.error(f"Request failed: {exc}")
            # Keep the user message in history; it can be retried in a new turn.
