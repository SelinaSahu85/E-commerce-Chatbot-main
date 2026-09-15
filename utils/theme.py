import streamlit as st


def apply_app_theme():
    """
    Apply the common white and light-blue theme to every page.
    """

    st.markdown(
        """
        <style>
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            background-color: #ffffff !important;
            color: #0f172a !important;
        }

        [data-testid="stHeader"] {
            background-color: #ffffff !important;
        }

        .main .block-container {
            background-color: #ffffff !important;
            max-width: 1100px !important;
            padding-top: 3rem !important;
            padding-bottom: 8rem !important;
        }

        h1,
        h2,
        h3,
        h4,
        h5,
        h6,
        p,
        label,
        li,
        span {
            color: #0f172a !important;
        }

        [data-testid="stSidebar"],
        [data-testid="stSidebarContent"],
        [data-testid="stSidebarNav"] {
            background-color: #eff6ff !important;
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid #bfdbfe !important;
        }

        [data-testid="stSidebar"] * {
            color: #0f172a !important;
        }

        [data-testid="stSidebarNav"] a {
            border-radius: 10px !important;
            margin-bottom: 4px !important;
        }

        [data-testid="stSidebarNav"] a:hover {
            background-color: #dbeafe !important;
        }

        [data-testid="stSidebarNav"] a[aria-current="page"] {
            background-color: #bfdbfe !important;
            color: #1e3a8a !important;
            font-weight: 600 !important;
        }

        [data-testid="stSelectbox"]
        div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #93c5fd !important;
            border-radius: 10px !important;
        }

        [data-testid="stChatMessage"] {
            background-color: #f8fbff !important;
            border: 1px solid #dbeafe !important;
            border-radius: 14px !important;
        }

        [data-testid="stBottom"],
        [data-testid="stBottomBlockContainer"] {
            background-color: #ffffff !important;
        }

        [data-testid="stChatInput"] {
            background-color: #eff6ff !important;
            border: 1px solid #93c5fd !important;
            border-radius: 16px !important;
        }

        [data-testid="stChatInput"] textarea {
            background-color: #ffffff !important;
            color: #0f172a !important;
        }

        [data-testid="stFileUploader"] {
            background-color: #eff6ff !important;
            border: 1px solid #93c5fd !important;
            border-radius: 14px !important;
            padding: 16px !important;
        }

        [data-testid="stFileUploaderDropzone"] {
            background-color: #ffffff !important;
            border: 2px dashed #60a5fa !important;
            border-radius: 12px !important;
        }

        .stButton > button {
            background-color: #2563eb !important;
            color: #ffffff !important;
            border: 1px solid #2563eb !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
        }

        .stButton > button:hover {
            background-color: #1d4ed8 !important;
            color: #ffffff !important;
        }

        [data-testid="stAlert"] {
            background-color: #eff6ff !important;
            color: #0f172a !important;
            border: 1px solid #bfdbfe !important;
            border-radius: 12px !important;
        }

        [data-testid="stAlert"] p,
        [data-testid="stAlert"] div {
            color: #0f172a !important;
        }

        input,
        textarea {
            background-color: #ffffff !important;
            color: #0f172a !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )