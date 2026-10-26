import json
import uuid
from datetime import datetime, timezone

import streamlit as st
from openai import OpenAI
from supabase import create_client

st.set_page_config(
    page_title="Nemotron",
    page_icon="✻",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Server-side secrets only. Never put these values in GitHub or the UI.
try:
    NVIDIA_API_KEY = st.secrets["NVIDIA_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except (KeyError, FileNotFoundError):
    st.error("The app owner must configure NVIDIA_API_KEY, SUPABASE_URL, and SUPABASE_KEY in Streamlit Secrets.")
    st.stop()

MODEL_ID = st.secrets.get("NVIDIA_MODEL_ID", "nvidia/nemotron-3-ultra-550b-a55b")
st.markdown("""
<style>
:root { --bg:#FAF9F5; --side:#F0EEE6; --text:#3D3929; --muted:#83827D; --accent:#C96442; --line:#E3E0D5; }
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background:var(--bg) !important; color:var(--text) !important; }
[data-testid="stHeader"] { background:var(--bg) !important; }
#MainMenu, footer { visibility:hidden; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background:var(--side) !important; border-right:1px solid var(--line); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] button,
[data-testid="stSidebar"] button span,
[data-testid="stSidebar"] input { color:var(--text) !important; }
[data-testid="stSidebar"] > div:first-child { padding-top:.65rem !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:.38rem !important; }
[data-testid="stSidebar"] [data-testid="stElementContainer"] { margin-bottom:0 !important; }
[data-testid="stSidebarCollapsedControl"] { visibility:visible !important; display:flex !important; }
h1,h2,h3,.brand,.welcome { font-family:Georgia,"Times New Roman",serif !important; font-weight:400 !important; color:var(--text) !important; }
.brand { font-size:1.45rem; margin:0 0 .25rem .1rem; }
.brand span,.welcome span { color:var(--accent); }
.sec { font-size:.76rem; color:var(--muted); margin:.35rem 0 .1rem .15rem; }
.welcome { text-align:center; font-size:2.35rem; margin-top:12vh; line-height:1.3; }
.welcome span { margin-right:8px; }
.sub { text-align:center; color:var(--muted); }
[data-testid="stChatMessage"] { background:transparent; padding:.25rem 0; }
[data-testid="stChatMessageAvatarUser"],[data-testid="stChatMessageAvatarAssistant"] { display:none; }
[data-testid="stExpander"] { border:1px solid var(--line) !important; border-radius:10px; background:transparent; }
.stButton > button, [data-testid="stFormSubmitButton"] button { border-radius:9px !important; border:1px solid transparent !important; color:var(--text) !important; background:transparent !important; min-height:2.15rem !important; padding:.35rem .55rem !important; line-height:1.15 !important; font-size:.88rem !important; }
.stButton > button span, [data-testid="stFormSubmitButton"] button span { color:var(--text) !important; visibility:visible !important; opacity:1 !important; }
.stButton > button:hover { background:#E6E3D8 !important; border-color:var(--line) !important; }
[data-testid="stSidebar"] input,[data-testid="stSidebar"] textarea { background:white !important; border-radius:9px !important; }
div[data-testid="stTextInput"] input { border-radius:10px; }
[data-testid="stSidebar"] [data-testid="stExpander"] details summary { padding:.35rem .55rem !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] { margin:0 !important; }
</style>
""", unsafe_allow_html=True)


S = st.session_state
S.setdefault("chats", {})
S.setdefault("projects", {"Personal": {"description": "General conversations"}})
S.setdefault("current", None)
S.setdefault("thinking", False)
S.setdefault("draft", "")
S.setdefault("authenticated", False)
S.setdefault("user", None)
S.setdefault("supabase", None)
S.setdefault("loaded_user_id", None)

# ---------- Authentication ----------
def get_client():
    if S.get("supabase") is None:
        S.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return S.supabase

def sign_out():
    try:
        if S.get("supabase") is not None:
            S.supabase.auth.sign_out()
    except Exception:
        pass
    for key in ("authenticated", "user", "loaded_user_id", "supabase", "chats", "current"):
        S.pop(key, None)
    S.authenticated = False
    S.user = None
    S.supabase = None
    S.chats = {}
    S.current = None
    st.rerun()

def auth_screen():
    st.markdown('<div class="brand"><span>✻</span> Nemotron</div>', unsafe_allow_html=True)
    st.subheader("Sign in to your account")
    st.caption("Your conversations are saved to your account and are private to you.")
    mode = st.radio("Choose an option", ["Sign in", "Create account"], horizontal=True)
    with st.form("auth_form"):
        email = st.text_input("Email", autocomplete="email")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in" if mode == "Sign in" else "Create account", use_container_width=True)
    if submitted:
        if not email.strip() or not password:
            st.error("Enter your email and password.")
            return
        try:
            client = get_client()
            if mode == "Sign in":
                result = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
                user = result.user
                if not user:
                    st.error("Sign-in did not return a user. Check your credentials and try again.")
                    return
                S.user = {"id": user.id, "email": user.email}
                S.authenticated = True
                S.loaded_user_id = None
                st.rerun()
            else:
                result = client.auth.sign_up({"email": email.strip(), "password": password})
                if result.user and not result.session:
                    st.success("Account created. Check your email to confirm the account, then return here and sign in.")
                elif result.user and result.session:
                    S.user = {"id": result.user.id, "email": result.user.email}
                    S.authenticated = True
                    S.loaded_user_id = None
                    st.rerun()
                else:
                    st.info("If account confirmation is enabled, check your email before signing in.")
        except Exception as exc:
            st.error(f"Authentication failed: {exc}")

if not S.get("authenticated") or not S.get("user"):
    auth_screen()
    st.stop()

# Recreate a client if necessary, and load only this signed-in user's rows.
client = get_client()
user_id = S.user["id"]
if S.get("loaded_user_id") != user_id:
    try:
        rows = client.table("chat_sessions").select("id,title,project_name,messages,created_at,updated_at").order("updated_at", desc=True).execute().data or []
        loaded_chats = {}
        project_names = {"Personal": {"description": "General conversations"}}
        for row in rows:
            cid = str(row["id"])
            project = row.get("project_name")
            loaded_chats[cid] = {
                "title": row.get("title") or "New chat",
                "messages": row.get("messages") or [],
                "pinned": False,
                "project": project,
                "updated_at": row.get("updated_at") or row.get("created_at") or "",
            }
            if project:
                project_names.setdefault(project, {"description": ""})
        S.chats = loaded_chats
        S.projects = project_names
        S.loaded_user_id = user_id
    except Exception as exc:
        st.error(f"Could not load your saved chats from Supabase: {exc}")
        st.stop()

def persist_chat(cid):
    chat = S.chats[cid]
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": cid,
        "user_id": user_id,
        "title": chat.get("title") or "New chat",
        "project_name": chat.get("project"),
        "messages": chat.get("messages", []),
        "updated_at": now,
    }
    client.table("chat_sessions").upsert(record, on_conflict="id").execute()
    chat["updated_at"] = now

def new_chat():
    S.current = None
    S.draft = ""

def open_chat(cid):
    S.current = cid

def delete_chat(cid):
    try:
        client.table("chat_sessions").delete().eq("id", cid).eq("user_id", user_id).execute()
        S.chats.pop(cid, None)
        if S.current == cid:
            S.current = None
    except Exception as exc:
        st.error(f"Could not delete chat: {exc}")

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
    title = (c.get("title") or "New chat").strip()
    if len(title) > 32:
        title = title[:31] + "…"
    st.button(
        f"◦  {title}",
        key=f"open_{cid}",
        on_click=open_chat,
        args=(cid,),
        use_container_width=True,
        help=c.get("title", "Open chat"),
    )
    action_col1, action_col2 = st.columns([1, 1], gap="small")
    action_col1.button(
        "☆ Pin" if not c.get("pinned") else "★ Pinned",
        key=f"pin_{cid}",
        on_click=toggle_pin,
        args=(cid,),
        use_container_width=True,
    )
    action_col2.button(
        "× Delete",
        key=f"delete_{cid}",
        on_click=delete_chat,
        args=(cid,),
        use_container_width=True,
    )

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown('<div class="brand"><span>✻</span> Nemotron</div>', unsafe_allow_html=True)
    st.caption(S.user.get("email", "Signed in"))
    st.button("Sign out", on_click=sign_out, use_container_width=True)
    st.button("＋  New chat", on_click=new_chat, use_container_width=True)
    search = st.text_input("Search chats", placeholder="🔍  Search chats", label_visibility="collapsed", key="search").strip().lower()

    st.markdown('<div class="sec">Projects</div>', unsafe_allow_html=True)
    project_names = list(S.projects.keys())
    selected_project = st.selectbox("Filter by project", ["All projects"] + project_names, label_visibility="collapsed", key="project_filter")
    with st.expander("＋ Create project"):
        st.text_input("Project name", key="new_project_name", placeholder="e.g. Risk Analytics")
        st.text_input("Description (optional)", key="new_project_description", placeholder="What is this project for?")
        st.button("Create project", on_click=create_project, use_container_width=True)

    for pname in project_names:
        project_chats = [cid for cid, c in S.chats.items() if c.get("project") == pname]
        with st.expander(f"📁 {pname} ({len(project_chats)})", expanded=(selected_project == pname)):
            for cid in reversed(project_chats):
                if cid in S.chats and (not search or search in S.chats[cid].get("title", "").lower() or any(search in m.get("content", "").lower() for m in S.chats[cid].get("messages", []))):
                    render_chat_button(cid)

    st.markdown('<div class="sec">Recent chats</div>', unsafe_allow_html=True)
    chat_ids = sorted(
        S.chats.keys(),
        key=lambda cid: (S.chats[cid].get("updated_at") or "", cid),
        reverse=True,
    )
    if selected_project != "All projects":
        chat_ids = [cid for cid in chat_ids if S.chats[cid].get("project") == selected_project]
    chat_ids = [cid for cid in chat_ids if not search or search in S.chats[cid].get("title", "").lower() or any(search in m.get("content", "").lower() for m in S.chats[cid].get("messages", []))]
    for cid in chat_ids:
        if selected_project == "All projects" and S.chats[cid].get("project"):
            continue
        render_chat_button(cid)

    with st.expander("Settings"):
        st.caption("NVIDIA and Supabase credentials are configured securely by the site owner.")
        S.user_name = st.text_input("Your name", value=S.get("user_name", "there"), key="display_name")
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
chat = S.chats.get(S.current) if S.current else None
messages = chat.get("messages", []) if isinstance(chat, dict) else []
if isinstance(chat, dict):
    st.caption(f"{chat.get('project') or 'No project'} · {chat.get('title') or 'New chat'}")
if not messages:
    st.markdown(f'<div class="welcome"><span>✻</span> Hi, {S.get("user_name", "there")}</div>', unsafe_allow_html=True)
    st.markdown('<p class="sub">What would you like to explore today?</p>', unsafe_allow_html=True)
for m in messages:
    with st.chat_message(m.get("role", "assistant")):
        if m.get("reasoning"):
            with st.expander("Thinking"):
                st.markdown(m["reasoning"])
        st.markdown(m.get("content", ""))

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
        cid = str(uuid.uuid4())
        title = prompt.strip().splitlines()[0][:40] or "New chat"
        default_project = selected_project if selected_project != "All projects" else None
        chat = {"title": title, "messages": [], "pinned": False, "project": default_project}
        S.chats[cid] = chat
        S.current = cid
        messages = chat["messages"]
    else:
        cid = S.current

    messages.append({"role": "user", "content": prompt.strip()})
    if len(messages) == 1:
        chat["title"] = prompt.strip().splitlines()[0][:40] or "New chat"
    api_messages = [{"role": "system", "content": S.get("system_prompt", "You are a helpful assistant.")}]
    api_messages.extend({"role": m["role"], "content": m["content"]} for m in messages if m.get("role") in ("user", "assistant"))
    with st.chat_message("user"):
        st.markdown(prompt.strip())
    with st.chat_message("assistant"):
        try:
            client_ai = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=NVIDIA_API_KEY)
            stream = client_ai.chat.completions.create(
                model=MODEL_ID,
                messages=api_messages,
                temperature=S.get("temperature", 0.7),
                top_p=0.95,
                max_tokens=S.get("max_tokens", 4096),
                extra_body={"chat_template_kwargs": {"enable_thinking": S.get("thinking", False)}},
                stream=True,
            )
            reasoning, reply = "", ""
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
            try:
                persist_chat(cid)
            except Exception as db_exc:
                st.error(f"The reply was generated, but saving the chat failed: {db_exc}")
            st.rerun()
        except Exception as exc:
            st.error(f"Request failed: {exc}")
            try:
                persist_chat(cid)
            except Exception as db_exc:
                st.warning(f"The message could not be saved: {db_exc}")
