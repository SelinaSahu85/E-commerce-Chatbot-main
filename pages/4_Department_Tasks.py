import streamlit as st

from utils.theme import apply_app_theme


st.set_page_config(
    page_title="Department Tasks",
    page_icon="✅",
    layout="wide",
)

apply_app_theme()

from database.schema import ensure_tables_exist
from database.repositories import DepartmentRepository
from hitl import department_review

ensure_tables_exist()

st.set_page_config(page_title="Department Tasks")
st.title("Department Tasks")

departments_df = DepartmentRepository.all()

department_names = (
    departments_df["department_name"].tolist()
    if not departments_df.empty
    else []
)

department = st.sidebar.selectbox("Department", department_names)

if department:

    pending = department_review.pending_tasks(department)

    if pending.empty:
        st.info(f"No pending tasks for {department}.")
    else:

        for _, task in pending.iterrows():

            with st.expander(f"{task['task_id']} — {task['action']} (Case {task['case_id']})"):

                st.write(f"**Resolution:** {task['resolution']}")
                st.write(f"**Created:** {task['created_date']}")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Approve / Complete", key=f"approve_{task['task_id']}"):
                        result = department_review.approve_task(task["task_id"])
                        if result["ok"]:
                            st.success("Task completed, case advanced.")
                        else:
                            st.warning(result["reason"])
                        st.rerun()

                with col2:
                    reason = st.text_input("Rejection reason", key=f"reason_{task['task_id']}")
                    if st.button("Reject", key=f"reject_{task['task_id']}"):
                        department_review.reject_task(
                            task["task_id"], reason or "Rejected by department"
                        )
                        st.success("Task rejected, case escalated.")
                        st.rerun()
