import streamlit as st
from dotenv import load_dotenv

from database.repositories import CustomerRepository
from database.schema import ensure_tables_exist
from graph.workflow import graph
from tools.evidence_upload import save_complaint_evidence
from utils.logger import logger
from utils.theme import apply_app_theme


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


# =========================================================
# PAGE CONFIGURATION
# This must be the first Streamlit command.
# =========================================================

st.set_page_config(
    page_title="E-Commerce Support Assistant",
    page_icon="🛒",
    layout="wide",
)


# =========================================================
# SHARED WHITE AND LIGHT-BLUE THEME
# =========================================================

apply_app_theme()


# =========================================================
# INITIALIZE DATASETS
# =========================================================

ensure_tables_exist()


# =========================================================
# PAGE HEADER
# =========================================================

st.title("🛒 E-Commerce Customer Support Assistant")

st.caption(
    "Ask a question, raise a complaint, upload evidence, "
    "or check the latest complaint status."
)


# =========================================================
# LOAD CUSTOMERS
# =========================================================

customers_df = CustomerRepository.all()

if (
    not customers_df.empty
    and "customer_id" in customers_df.columns
):
    customer_ids = (
        customers_df["customer_id"]
        .astype(str)
        .str.strip()
        .tolist()
    )
else:
    customer_ids = ["CUST001"]


# =========================================================
# CUSTOMER LOGIN
# =========================================================

customer_id = st.sidebar.selectbox(
    "Logged in as",
    customer_ids,
    key="app_customer_login_selector",
)

st.sidebar.caption(
    "This selector simulates customer login for the MVP. "
    "Human review pages are available under the Pages menu."
)


# =========================================================
# DEFAULT COMPLAINT STATE
# =========================================================

def get_default_complaint_data():
    """
    Return a clean complaint conversation state.
    """

    return {
        "customer_id": customer_id,
        "order_id": "",
        "case_id": "",
        "issue_type": "",
        "description": "",
        "complaint_status": "",
        "pending_field": "",
        "evidence_id": "",
        "evidence_path": "",
    }


# =========================================================
# SESSION STATE INITIALIZATION
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "complaint_data" not in st.session_state:
    st.session_state.complaint_data = (
        get_default_complaint_data()
    )

if "selected_customer_id" not in st.session_state:
    st.session_state.selected_customer_id = customer_id


# =========================================================
# RESET WHEN CUSTOMER CHANGES
# =========================================================

if st.session_state.selected_customer_id != customer_id:
    logger.info(
        "Customer changed from %s to %s. "
        "Resetting conversation.",
        st.session_state.selected_customer_id,
        customer_id,
    )

    st.session_state.selected_customer_id = customer_id
    st.session_state.messages = []
    st.session_state.complaint_data = (
        get_default_complaint_data()
    )

    if "complaint_evidence_uploader" in st.session_state:
        del st.session_state[
            "complaint_evidence_uploader"
        ]

    st.rerun()


# =========================================================
# HELPER: SAVE GRAPH RESULT
# =========================================================

def save_graph_result(result):
    """
    Save complaint-related fields returned by the graph
    into Streamlit session state.
    """

    fields_to_preserve = [
        "customer_id",
        "order_id",
        "case_id",
        "issue_type",
        "description",
        "complaint_status",
        "pending_field",
        "evidence_id",
        "evidence_path",
    ]

    updated_data = dict(
        st.session_state.complaint_data
    )

    for field in fields_to_preserve:
        if field in result:
            returned_value = result.get(field)

            if returned_value is not None:
                updated_data[field] = returned_value

    st.session_state.complaint_data = updated_data

    logger.info(
        "Complaint context saved. "
        "Order ID=%s, Case ID=%s, Status=%s, Pending=%s",
        updated_data.get("order_id"),
        updated_data.get("case_id"),
        updated_data.get("complaint_status"),
        updated_data.get("pending_field"),
    )


# =========================================================
# HELPER: BUILD RESPONSE
# =========================================================

def build_bot_response(result):
    """
    Build the final response from the graph result.
    """

    bot_response = str(
        result.get(
            "response",
            "",
        )
    ).strip()

    if not bot_response:
        logger.error(
            "Graph returned an empty response. Result=%s",
            result,
        )

        bot_response = (
            "I processed your request, but I could not "
            "generate a response. Please try again."
        )

    sources = result.get(
        "sources",
        [],
    )

    if sources:
        source_text = ", ".join(
            str(source)
            for source in sources
            if source
        )

        if source_text:
            bot_response += (
                "\n\n**Sources:** "
                + source_text
            )

    return bot_response


# =========================================================
# SIDEBAR COMPLAINT CONTEXT
# =========================================================

complaint_data = st.session_state.complaint_data

st.sidebar.divider()
st.sidebar.subheader("Current Complaint Context")

st.sidebar.write(
    "**Order ID:**",
    complaint_data.get("order_id") or "Not provided",
)

st.sidebar.write(
    "**Case ID:**",
    complaint_data.get("case_id") or "Not available",
)

st.sidebar.write(
    "**Complaint Status:**",
    complaint_data.get("complaint_status") or "Not started",
)

st.sidebar.write(
    "**Waiting For:**",
    complaint_data.get("pending_field") or "Customer message",
)

if complaint_data.get("evidence_id"):
    st.sidebar.write(
        "**Evidence ID:**",
        complaint_data.get("evidence_id"),
    )


# =========================================================
# START NEW CONVERSATION
# =========================================================

if st.sidebar.button(
    "Start New Conversation",
    key="app_start_new_conversation",
    use_container_width=True,
):
    st.session_state.messages = []

    st.session_state.complaint_data = (
        get_default_complaint_data()
    )

    if "complaint_evidence_uploader" in st.session_state:
        del st.session_state[
            "complaint_evidence_uploader"
        ]

    st.rerun()


# =========================================================
# DISPLAY CHAT HISTORY
# =========================================================

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# =========================================================
# CURRENT PENDING FIELD
# =========================================================

pending_field = str(
    st.session_state.complaint_data.get(
        "pending_field",
        "",
    )
).strip().lower()


# =========================================================
# IMAGE EVIDENCE UPLOAD
# =========================================================

if pending_field == "image_evidence":
    st.markdown(
        """
        <div class="evidence-box">
            <h3>📷 Upload Complaint Evidence</h3>
            <p>
                Upload a clear image showing the product and
                the reported issue. The image will be sent to
                a human reviewer for verification.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Select an image",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
        key="complaint_evidence_uploader",
        help=(
            "Upload a clear PNG, JPG, JPEG, or WEBP image "
            "showing the reported issue."
        ),
    )

    if uploaded_file is not None:
        st.image(
            uploaded_file,
            caption="Evidence image preview",
            width=500,
        )

        file_size_mb = (
            uploaded_file.size
            / (1024 * 1024)
        )

        st.caption(
            f"File: {uploaded_file.name} | "
            f"Size: {file_size_mb:.2f} MB"
        )

        if file_size_mb > 5:
            st.error(
                "The image is larger than 5 MB. "
                "Please upload a smaller image."
            )

        else:
            submit_evidence = st.button(
                "Submit Evidence for Human Review",
                key="app_submit_evidence",
                type="primary",
                use_container_width=True,
            )

            if submit_evidence:
                current_case_id = str(
                    st.session_state.complaint_data.get(
                        "case_id",
                        "",
                    )
                ).strip()

                current_order_id = str(
                    st.session_state.complaint_data.get(
                        "order_id",
                        "",
                    )
                ).strip()

                if not current_case_id:
                    st.error(
                        "Case ID is missing. Please enter "
                        "the Order ID again."
                    )

                elif not current_order_id:
                    st.error(
                        "Order ID is missing. Please enter "
                        "the Order ID again."
                    )

                else:
                    try:
                        with st.spinner(
                            "Submitting evidence for review..."
                        ):
                            evidence = (
                                save_complaint_evidence(
                                    uploaded_file=uploaded_file,
                                    case_id=current_case_id,
                                    order_id=current_order_id,
                                )
                            )

                        if not evidence:
                            raise ValueError(
                                "Evidence upload returned no result."
                            )

                        evidence_id = str(
                            evidence.get(
                                "evidence_id",
                                "",
                            )
                        ).strip()

                        evidence_path = str(
                            evidence.get(
                                "file_path",
                                "",
                            )
                        ).strip()

                        updated_data = dict(
                            st.session_state.complaint_data
                        )

                        updated_data[
                            "evidence_id"
                        ] = evidence_id

                        updated_data[
                            "evidence_path"
                        ] = evidence_path

                        updated_data[
                            "pending_field"
                        ] = "evidence_review"

                        updated_data[
                            "complaint_status"
                        ] = (
                            updated_data.get(
                                "complaint_status",
                                "",
                            )
                            or "OPEN"
                        )

                        st.session_state.complaint_data = (
                            updated_data
                        )

                        confirmation_message = (
                            "✅ **Evidence submitted successfully**\n\n"
                            f"**Evidence ID:** {evidence_id}\n\n"
                            f"**Case ID:** {current_case_id}\n\n"
                            f"**Order ID:** {current_order_id}\n\n"
                            "The image has been sent to our "
                            "customer-care team for human review. "
                            "After the reviewer completes the review, "
                            "click **Refresh Evidence Review Status**."
                        )

                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": confirmation_message,
                            }
                        )

                        logger.info(
                            "Evidence submitted. "
                            "Evidence ID=%s, Case ID=%s, Order ID=%s",
                            evidence_id,
                            current_case_id,
                            current_order_id,
                        )

                        st.rerun()

                    except Exception as exc:
                        logger.exception(
                            "Evidence upload failed: %s",
                            exc,
                        )

                        st.error(
                            f"Evidence upload failed: {exc}"
                        )


# =========================================================
# EVIDENCE REVIEW STATUS
# =========================================================

elif pending_field == "evidence_review":
    evidence_id = str(
        complaint_data.get(
            "evidence_id",
            "",
        )
    ).strip()

    current_case_id = str(
        complaint_data.get(
            "case_id",
            "",
        )
    ).strip()

    current_order_id = str(
        complaint_data.get(
            "order_id",
            "",
        )
    ).strip()

    st.markdown(
        f"""
        <div class="evidence-review-box">
            <h3>🔎 Evidence Under Human Review</h3>
            <p>
                The uploaded evidence is waiting for review
                by the customer-care team.
            </p>
            <p>
                <strong>Evidence ID:</strong>
                {evidence_id or "Pending"}
            </p>
            <p>
                <strong>Case ID:</strong>
                {current_case_id or "Not available"}
            </p>
            <p>
                <strong>Order ID:</strong>
                {current_order_id or "Not available"}
            </p>
            <p>
                After the reviewer completes the review, click
                the button below to check the latest status.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    refresh_clicked = st.button(
        "🔄 Refresh Evidence Review Status",
        key="app_refresh_evidence_status",
        type="primary",
        use_container_width=True,
    )

    if refresh_clicked:
        if not current_order_id:
            st.error(
                "Order ID is missing. Please start a new "
                "conversation and enter the Order ID again."
            )

        else:
            refresh_state = {
                "user_query": (
                    "Check my evidence review status"
                ),
                "customer_id": customer_id,
                "intent": "complaint",
                "response": "",
                "sources": [],
                "requires_hitl": True,
                "review_id": "",
                "case_id": current_case_id,
                "order_id": current_order_id,
                "issue_type": complaint_data.get(
                    "issue_type",
                    "",
                ),
                "description": complaint_data.get(
                    "description",
                    "",
                ),
                "complaint_status": complaint_data.get(
                    "complaint_status",
                    "",
                ),
                "pending_field": "evidence_review",
                "evidence_id": evidence_id,
                "evidence_path": complaint_data.get(
                    "evidence_path",
                    "",
                ),
            }

            try:
                logger.info(
                    "Refreshing evidence review status. "
                    "Evidence ID=%s, Case ID=%s, Order ID=%s",
                    evidence_id,
                    current_case_id,
                    current_order_id,
                )

                with st.spinner(
                    "Checking the latest review status..."
                ):
                    result = graph.invoke(
                        refresh_state
                    )

                if not result:
                    raise ValueError(
                        "The graph returned no result."
                    )

                save_graph_result(
                    result
                )

                bot_response = build_bot_response(
                    result
                )

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": bot_response,
                    }
                )

                logger.info(
                    "Evidence review status refreshed. "
                    "Case ID=%s, Status=%s, Pending=%s",
                    st.session_state.complaint_data.get(
                        "case_id"
                    ),
                    st.session_state.complaint_data.get(
                        "complaint_status"
                    ),
                    st.session_state.complaint_data.get(
                        "pending_field"
                    ),
                )

                st.rerun()

            except Exception as exc:
                logger.exception(
                    "Evidence status refresh failed: %s",
                    exc,
                )

                st.error(
                    "Unable to refresh the evidence-review "
                    f"status: {exc}"
                )


# =========================================================
# CHAT INPUT
# =========================================================

user_input = st.chat_input(
    "Ask a question or raise a complaint...",
    key="app_chat_input",
)


# =========================================================
# PROCESS CHAT MESSAGE
# =========================================================

if user_input:
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    try:
        complaint_data = (
            st.session_state.complaint_data
        )

        current_pending_field = str(
            complaint_data.get(
                "pending_field",
                "",
            )
        ).strip().lower()

        if current_pending_field == "issue_type":
            complaint_data[
                "issue_type"
            ] = user_input

        elif current_pending_field == "description":
            complaint_data[
                "description"
            ] = user_input

        # Do not set order_id here.
        # The Complaint Agent extracts and validates it.

        state = {
            "user_query": user_input,
            "customer_id": customer_id,
            "intent": "",
            "response": "",
            "sources": [],
            "requires_hitl": False,
            "review_id": "",
            "case_id": complaint_data.get(
                "case_id",
                "",
            ),
            "order_id": complaint_data.get(
                "order_id",
                "",
            ),
            "issue_type": complaint_data.get(
                "issue_type",
                "",
            ),
            "description": complaint_data.get(
                "description",
                "",
            ),
            "complaint_status": complaint_data.get(
                "complaint_status",
                "",
            ),
            "pending_field": complaint_data.get(
                "pending_field",
                "",
            ),
            "evidence_id": complaint_data.get(
                "evidence_id",
                "",
            ),
            "evidence_path": complaint_data.get(
                "evidence_path",
                "",
            ),
        }

        logger.info(
            "Invoking graph. "
            "Customer=%s, Pending=%s, Order=%s, Case=%s",
            customer_id,
            state.get("pending_field"),
            state.get("order_id"),
            state.get("case_id"),
        )

        with st.chat_message("assistant"):
            with st.spinner(
                "Processing your request..."
            ):
                result = graph.invoke(
                    state
                )

            if not result:
                raise ValueError(
                    "The graph returned no result."
                )

            logger.info(
                "Graph result. "
                "Intent=%s, Order=%s, Case=%s, "
                "Status=%s, Pending=%s",
                result.get("intent"),
                result.get("order_id"),
                result.get("case_id"),
                result.get("complaint_status"),
                result.get("pending_field"),
            )

            save_graph_result(
                result
            )

            bot_response = build_bot_response(
                result
            )

            st.markdown(
                bot_response
            )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": bot_response,
            }
        )

        logger.info(
            "Response saved. "
            "Order=%s, Case=%s, Status=%s, Pending=%s",
            st.session_state.complaint_data.get(
                "order_id"
            ),
            st.session_state.complaint_data.get(
                "case_id"
            ),
            st.session_state.complaint_data.get(
                "complaint_status"
            ),
            st.session_state.complaint_data.get(
                "pending_field"
            ),
        )

        # Redraw the page so the sidebar immediately shows
        # the latest Order ID, Case ID and complaint status.
        st.rerun()

    except Exception as exc:
        logger.exception(
            "Chat processing failed: %s",
            exc,
        )

        error_message = (
            "Something went wrong while processing your request. "
            "Please try again."
        )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": error_message,
            }
        )

        with st.chat_message("assistant"):
            st.error(
                error_message
            )