import os
import streamlit as st
import pandas as pd
from pypdf import PdfReader
from google import genai

st.set_page_config(page_title="Compliance Queries", page_icon="⚖️", layout="wide")

DOCS_DIR = "documents"
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))

if not API_KEY:
    st.error("Missing Gemini API Key. Please configure GEMINI_API_KEY in Streamlit Cloud Secrets.")
    st.stop()

client = genai.Client(api_key=API_KEY)

# -------------------------------------------------------------
# Knowledge Base Builder (In-Memory Processing)
# -------------------------------------------------------------
@st.cache_data
def load_all_policy_text():
    combined_knowledge = []
    if not os.path.exists(DOCS_DIR):
        return ""

    files = [f for f in os.listdir(DOCS_DIR) if not f.startswith('.')]
    for file_name in files:
        file_path = os.path.join(DOCS_DIR, file_name)

        # 1. Process PDFs
        if file_name.lower().endswith(".pdf"):
            try:
                reader = PdfReader(file_path)
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text:
                        combined_knowledge.append(f"[{file_name} - Page {page_num + 1}]:\n{text}")
            except Exception as e:
                st.error(f"Error reading {file_name}: {e}")

        # 2. Process Excel Spreadsheets
        elif file_name.lower().endswith((".xlsx", ".xls")):
            try:
                sheets = pd.read_excel(file_path, sheet_name=None)
                for sheet_name, df in sheets.items():
                    for idx, row in df.iterrows():
                        row_items = [f"{col}: {val}" for col, val in row.items() if pd.notna(val)]
                        row_text = " | ".join(row_items)
                        if row_text.strip():
                            combined_knowledge.append(f"[{file_name} - Sheet: {sheet_name}, Row {idx + 1}]:\n{row_text}")
            except Exception as e:
                st.error(f"Error reading {file_name}: {e}")

    return "\n\n---\n\n".join(combined_knowledge)

# -------------------------------------------------------------
# Main Application UI
# -------------------------------------------------------------
st.title("⚖️ Compliance Queries")
st.caption("AI-powered compliance and policy assistant grounded strictly on internal company guidelines.")

with st.spinner("Indexing approved policy documents..."):
    knowledge_base = load_all_policy_text()

if not knowledge_base:
    st.warning("No policy documents found in the 'documents/' folder.")
    st.stop()

# Sidebar: Document Viewer
with st.sidebar:
    st.header("📋 Managed Policies")
    current_files = [f for f in os.listdir(DOCS_DIR) if not f.startswith('.')]
    for f in current_files:
        st.text(f"📄 {f}")

# Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_query = st.chat_input("Ask a question about HR, leave, travel, or statutory rules...")

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        with st.spinner("Reviewing policy guidelines..."):
            system_instruction = (
                "You are an internal corporate compliance and policy expert. "
                "Answer the user question strictly using ONLY the provided policy context below. "
                "Strict Guidelines:\n"
                "1. If the answer cannot be determined strictly from the provided context, state: "
                "'I am unable to find this information in the approved policy documents.'\n"
                "2. Do not invent, extrapolate, or guess policy terms.\n"
                "3. Always cite the exact source document name and page/sheet/row location where the rule was identified.\n\n"
                f"Policy Context:\n{knowledge_base}"
            )
            
            try:
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=[system_instruction, f"User Question: {user_query}"]
                )
                answer = response.text
            except Exception as err:
                answer = f"Error processing query: {err}"

            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
