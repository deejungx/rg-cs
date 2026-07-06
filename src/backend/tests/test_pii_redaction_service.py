from app.services.pii_redaction_service import PiiRedactionService
from src.shared.schemas import DocumentParseResult


def test_pii_redaction_service_redacts_email_phone_and_url() -> None:
    service = PiiRedactionService(
        enabled=True,
        language="en",
        entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "URL"],
    )

    text = (
        "Email jane.doe@example.com or call +1 555 123 4567. "
        "Portfolio: https://example.com/jane-doe"
    )

    redacted = service.redact_text(text)

    assert "jane.doe@example.com" not in redacted
    assert "+1 555 123 4567" not in redacted
    assert "https://example.com/jane-doe" not in redacted
    assert "<EMAIL_ADDRESS>" in redacted
    assert "<PHONE_NUMBER>" in redacted
    assert "<URL>" in redacted


def test_redact_parse_result_preserves_source_text_for_internal_use() -> None:
    service = PiiRedactionService(
        enabled=True,
        language="en",
        entities=["EMAIL_ADDRESS"],
    )
    parsed = DocumentParseResult(text="Contact jane.doe@example.com", parser="test")
    parsed.set_source_text(parsed.text)

    redacted = service.redact_parse_result(parsed)

    assert redacted.text == "Contact <EMAIL_ADDRESS>"
    assert redacted.source_text == "Contact jane.doe@example.com"
    assert redacted.redaction_applied is True
