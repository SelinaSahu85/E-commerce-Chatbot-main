import streamlit as st

from utils.theme import apply_app_theme


st.set_page_config(
    page_title="Customer Care",
    page_icon="🎧",
    layout="wide",
)

apply_app_theme()

from database.schema import ensure_tables_exist
from hitl import customer_care

ensure_tables_exist()

st.set_page_config(page_title="Customer Care")
st.title("Customer Care — Escalated Requests")

pending = customer_care.pending_reviews()

if pending.empty:
    st.info("No escalated requests pending.")
else:

    for _, row in pending.iterrows():

        with st.expander(f"{row['review_id']}"):

            st.write(f"**Query:** {row['query']}")

            response = st.text_area("Response to customer", key=f"resp_{row['review_id']}")

            if st.button("Resolve", key=f"resolve_{row['review_id']}"):
                customer_care.resolve_review(row["review_id"], response)
                st.success("Resolved.")
                st.rerun()
