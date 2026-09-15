import streamlit as st
from utils.theme import apply_app_theme

st.set_page_config(
page_title="Case Manager",
page_icon="📷",
layout="wide",
)

apply_app_theme()

from database.schema import ensure_tables_exist
from database.repositories import ComplaintRepository, OrderRepository
from hitl import case_manager

ensure_tables_exist()

st.set_page_config(page_title="Case Manager")
st.title("Case Manager — Pending Resolutions")

pending = case_manager.pending_recommendations()

if pending.empty:
    st.info("No cases awaiting Case Manager approval.")
else:

    for _, case in pending.iterrows():

        complaint = ComplaintRepository.get_by_case(case["case_id"]) or {}
        order = OrderRepository.get_by_id(case["order_id"]) or {}

        with st.expander(f"{case['case_id']} — {complaint.get('complaint_type', '')}"):

            st.write(f"**Customer:** {case['customer_id']}")
            st.write(f"**Order:** {case['order_id']} (amount: {order.get('amount', 'N/A')})")
            st.write(f"**Complaint:** {complaint.get('complaint_text', '')}")
            st.write(f"**Requested resolution:** {complaint.get('requested_resolution', '')}")
            st.write(f"**AI recommended resolution:** {complaint.get('recommended_resolution', '')}")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Approve", key=f"approve_{case['case_id']}"):
                    result = case_manager.approve(case["case_id"])
                    if result["ok"]:
                        st.success("Approved.")
                    else:
                        st.error(result["reason"])
                    st.rerun()

            with col2:
                override = st.selectbox(
                    "Modify to",
                    ["refund", "replacement", "voucher"],
                    key=f"override_{case['case_id']}",
                )
                if st.button("Approve with modification", key=f"modify_{case['case_id']}"):
                    result = case_manager.approve(case["case_id"], override_resolution=override)
                    if result["ok"]:
                        st.success("Approved with modification.")
                    else:
                        st.error(result["reason"])
                    st.rerun()

            with col3:
                reason = st.text_input("Rejection reason", key=f"reason_{case['case_id']}")
                if st.button("Reject", key=f"reject_{case['case_id']}"):
                    case_manager.reject(case["case_id"], reason or "Not eligible under policy")
                    st.success("Rejected.")
                    st.rerun()
