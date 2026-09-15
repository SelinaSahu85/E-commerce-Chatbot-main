import uuid
from pathlib import Path

from database.repositories import EvidenceRepository
from utils.logger import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]

EVIDENCE_DIRECTORY = (
    PROJECT_ROOT / "uploaded_evidence"
)

ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


def save_complaint_evidence(
    uploaded_file,
    case_id,
    order_id,
):
    """
    Save an uploaded complaint image and create a pending
    evidence-review record.
    """

    if uploaded_file is None:
        raise ValueError(
            "No evidence image was uploaded."
        )

    normalized_case_id = str(
        case_id or ""
    ).strip().upper()

    normalized_order_id = str(
        order_id or ""
    ).strip().upper()

    if not normalized_case_id:
        raise ValueError(
            "Case ID is required for evidence upload."
        )

    if not normalized_order_id:
        raise ValueError(
            "Order ID is required for evidence upload."
        )

    original_name = Path(
        uploaded_file.name
    ).name

    file_extension = Path(
        original_name
    ).suffix.lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Only PNG, JPG, JPEG and WEBP images are allowed."
        )

    EVIDENCE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    unique_id = uuid.uuid4().hex[:8].upper()

    saved_name = (
        f"{normalized_case_id}_{unique_id}"
        f"{file_extension}"
    )

    saved_path = (
        EVIDENCE_DIRECTORY / saved_name
    )

    with open(saved_path, "wb") as output_file:
        output_file.write(
            uploaded_file.getbuffer()
        )

    evidence = EvidenceRepository.create_pending(
        case_id=normalized_case_id,
        order_id=normalized_order_id,
        file_path=str(saved_path),
        evidence_type="IMAGE",
        description=(
            "Customer uploaded an image for complaint verification"
        ),
    )

    logger.info(
        "Evidence image saved. "
        "Evidence ID=%s, File=%s",
        evidence.get("evidence_id"),
        saved_path,
    )

    return evidence