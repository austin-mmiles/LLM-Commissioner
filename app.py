# app.py
import os
import traceback
import streamlit as st
from espn_fetcher import get_week_matchups
from gpt_summarizer import generate_week_recap

# -------------------- Secrets/env bootstrap --------------------
def _maybe_env_from_secrets(key: str):
    try:
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = str(st.secrets[key])
    except Exception:
        pass  # st.secrets may not exist locally

for _k in ("OPENAI_API_KEY", "ESPN_S2", "SWID"):
    _maybe_env_from_secrets(_k)

# -------------------- Page --------------------
st.set_page_config(page_title="LLM Commissioner", page_icon="🏈", layout="wide")
st.title("LLM Commissioner – Weekly Recaps")

with st.sidebar:
    st.header("Credentials")
    st.caption("Provide these here if not set via environment or Streamlit Secrets.")
    openai = st.text_input("OPENAI_API_KEY", value=os.getenv("OPENAI_API_KEY", ""), type="password")
    s2 = st.text_input("ESPN_S2 (optional)", value=os.getenv("ESPN_S2", ""), type="password")
    swid = st.text_input("SWID (optional)", value=os.getenv("SWID", ""), type="password")
    if st.button("Save Credentials"):
        if openai:
            os.environ["OPENAI_API_KEY"] = openai
        if s2:
            os.environ["ESPN_S2"] = s2
        if swid:
            os.environ["SWID"] = swid
        st.success("Saved for this session.")

def _need_openai() -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Missing **OPENAI_API_KEY**. Add it in the sidebar or in Streamlit Secrets.")
        return True
    return False

col1, col2, col3 = st.columns(3)
with
