from pathlib import Path

import streamlit as st

from database.repositories import EvidenceRepository
from utils.logger import logger
from utils.theme import apply_app_theme


# =========================================================
# PAGE CONFIGURATION
# Only one set_page_config call is allowed per page.
# =========================================================

st.set_page_config(
    page_title="Evidence Reviewer",
    page_icon="📷",
    layout="wide",
)


# =========================================================
# APPLY SHARED WHITE AND LIGHT-BLUE THEME
# =========================================================

apply_app_theme()


# =========================================================
# PAGE HEADER
# =========================================================

st.title("📷 Complaint Evidence Reviewer")

st.caption(
    "Review customer-uploaded evidence and approve or reject "
    "the image before the complaint moves to the next stage."
)


# =========================================================
# LOAD PENDING EVIDENCE REVIEWS
# =========================================================

try:
    pending_reviews = EvidenceRepository.pending()

except Exception as exc:
    logger.exception(
        "Failed to load pending evidence reviews: %s",
        exc,
    )

    st.error(
        "Unable to load pending evidence reviews. "
        "Please check the application logs."
    )

    st.stop()


# =========================================================
# NO PENDING REVIEWS
# =========================================================

if pending_reviews.empty:
    st.info(
        "No evidence is currently pending review."
    )

    if st.button(
        "Refresh Reviews",
        key="refresh_empty_evidence_reviews",
        type="primary",
    ):
        st.rerun()

    st.stop()


# =========================================================
# REVIEW LIST SUMMARY
# =========================================================

st.success(
    f"{len(pending_reviews)} evidence review"
    f"{'s' if len(pending_reviews) != 1 else ''} pending."
)

if st.button(
    "Refresh Review Queue",
    key="refresh_evidence_review_queue",
):
    st.rerun()


# =========================================================
# DISPLAY EACH PENDING REVIEW
# =========================================================

for _, review in pending_reviews.iterrows():
    evidence_id = str(
        review.get("evidence_id", "")
    ).strip()

    case_id = str(
        review.get("case_id", "")
    ).strip()

    order_id = str(
        review.get("order_id", "")
    ).strip()

    evidence_type = str(
        review.get("evidence_type", "")
    ).strip()

    file_path = str(
        review.get("file_path", "")
    ).strip()

    description = str(
        review.get("description", "")
    ).strip()

    uploaded_at = str(
        review.get("uploaded_at", "")
    ).strip()

    result = str(
        review.get("result", "PENDING")
    ).strip()

    with st.container(border=True):
        st.subheader(
            f"Evidence ID: {evidence_id}"
        )

        detail_column, status_column = st.columns(
            [3, 1]
        )

        with detail_column:
            st.markdown(
                f"""
                **Case ID:** {case_id or "N/A"}  
                **Order ID:** {order_id or "N/A"}  
                **Evidence Type:** {evidence_type or "N/A"}  
                **Description:** {description or "N/A"}  
                **Uploaded At:** {uploaded_at or "N/A"}
                """
            )

        with status_column:
            st.info(
                f"Status: {result or 'PENDING'}"
            )

        st.divider()

        # =================================================
        # DISPLAY EVIDENCE IMAGE
        # =================================================

        if file_path:
            evidence_path = Path(file_path)

            if evidence_path.exists():
                st.image(
                    str(evidence_path),
                    caption=(
                        f"Uploaded evidence for case "
                        f"{case_id}"
                    ),
                    width=600,
                )

            else:
                logger.error(
                    "Evidence image not found. "
                    "Evidence ID=%s, File=%s",
                    evidence_id,
                    file_path,
                )

                st.error(
                    "The uploaded image file could not be found."
                )

                st.code(
                    file_path,
                    language=None,
                )

        else:
            st.error(
                "No file path is stored for this evidence."
            )

        st.divider()

        # =================================================
        # REVIEWER INPUT
        # =================================================

        reviewer_name = st.text_input(
            "Reviewed by",
            key=f"reviewer_name_{evidence_id}",
            placeholder="Enter reviewer name",
        )

        comments = st.text_area(
            "Reviewer comments",
            key=f"reviewer_comments_{evidence_id}",
            placeholder=(
                "Enter approval comments or explain why "
                "the evidence is being rejected."
            ),
            height=120,
        )

        approve_column, reject_column = st.columns(
            2
        )

        # =================================================
        # APPROVE EVIDENCE
        # =================================================

        with approve_column:
            approve_clicked = st.button(
                "✅ Approve Evidence",
                key=f"approve_evidence_{evidence_id}",
                type="primary",
                use_container_width=True,
            )

            if approve_clicked:
                if not reviewer_name.strip():
                    st.warning(
                        "Please enter the reviewer name "
                        "before approving the evidence."
                    )

                else:
                    try:
                        with st.spinner(
                            "Approving evidence and escalating "
                            "the complaint..."
                        ):
                            updated_count = (
                                EvidenceRepository.record_decision(
                                    evidence_id=evidence_id,
                                    result="APPROVED",
                                    comments=comments,
                                    reviewed_by=reviewer_name,
                                )
                            )

                        if updated_count > 0:
                            logger.info(
                                "Evidence approved. "
                                "Evidence ID=%s, Case ID=%s, "
                                "Reviewer=%s",
                                evidence_id,
                                case_id,
                                reviewer_name,
                            )

                            st.success(
                                "Evidence approved successfully. "
                                "The complaint has been escalated "
                                "to the assigned department."
                            )

                            st.rerun()

                        else:
                            st.error(
                                "The evidence record was not updated."
                            )

                    except Exception as exc:
                        logger.exception(
                            "Evidence approval failed. "
                            "Evidence ID=%s, Error=%s",
                            evidence_id,
                            exc,
                        )

                        st.error(
                            f"Evidence approval failed: {exc}"
                        )

        # =================================================
        # REJECT EVIDENCE
        # =================================================

        with reject_column:
            reject_clicked = st.button(
                "❌ Reject Evidence",
                key=f"reject_evidence_{evidence_id}",
                use_container_width=True,
            )

            if reject_clicked:
                if not reviewer_name.strip():
                    st.warning(
                        "Please enter the reviewer name "
                        "before rejecting the evidence."
                    )

                elif not comments.strip():
                    st.warning(
                        "Please provide a rejection reason so "
                        "the customer knows what image to upload."
                    )

                else:
                    try:
                        with st.spinner(
                            "Rejecting evidence..."
                        ):
                            updated_count = (
                                EvidenceRepository.record_decision(
                                    evidence_id=evidence_id,
                                    result="REJECTED",
                                    comments=comments,
                                    reviewed_by=reviewer_name,
                                )
                            )

                        if updated_count > 0:
                            logger.info(
                                "Evidence rejected. "
                                "Evidence ID=%s, Case ID=%s, "
                                "Reviewer=%s",
                                evidence_id,
                                case_id,
                                reviewer_name,
                            )

                            st.warning(
                                "Evidence rejected. The complaint "
                                "has been moved to Awaiting Customer, "
                                "and the customer will be asked to "
                                "upload a clearer image."
                            )

                            st.rerun()

                        else:
                            st.error(
                                "The evidence record was not updated."
                            )

                    except Exception as exc:
                        logger.exception(
                            "Evidence rejection failed. "
                            "Evidence ID=%s, Error=%s",
                            evidence_id,
                            exc,
                        )

                        st.error(
                            f"Evidence rejection failed: {exc}"
                        )