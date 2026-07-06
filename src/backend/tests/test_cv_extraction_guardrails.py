import json

from src.ai.crews.cv_extraction_crew import (
    _build_markdown_guardrail,
    _validate_profile_extraction_guardrail,
    _validate_resume_validation_guardrail,
)
from src.ai.formatters.cv_markdown import render_cv_markdown
from src.shared.schemas import ComprehensiveCvProfile, ResumeValidationResult


class DummyTaskOutput:
    def __init__(self, *, raw: str = "", pydantic=None, json_dict=None) -> None:
        self.raw = raw
        self.pydantic = pydantic
        self.json_dict = json_dict


def test_resume_validation_guardrail_requires_reason() -> None:
    passed, payload = _validate_resume_validation_guardrail(
        DummyTaskOutput(pydantic=ResumeValidationResult(is_resume=True, reason=""))
    )

    assert passed is False
    assert "reason field" in payload


def test_profile_extraction_guardrail_rejects_placeholders_and_inconsistent_dates() -> None:
    raw_profile = json.dumps(
        {
            "personal_info": {
                "firstname": "Jane",
                "lastname": "Doe",
                "note": "Unknown",
            },
            "professional_experience": {
                "primary_designation": "Senior Engineer",
                "work": [
                    {
                        "organization_name": "Example Corp",
                        "designations": ["Senior Engineer"],
                        "industry": "Technology/Software",
                        "key_responsibilities": ["Built APIs"],
                        "still_working": True,
                        "start": {"year": 2024, "month": 1},
                        "end": {"year": 2025, "month": 1},
                        "tools": ["FastAPI"],
                    }
                ],
            },
            "education_skills": {},
            "extraction_notes": [],
        }
    )

    passed, payload = _validate_profile_extraction_guardrail(
        DummyTaskOutput(raw=raw_profile)
    )

    assert passed is False
    assert "placeholder strings" in payload
    assert "current but also includes an end date" in payload


def test_markdown_guardrail_accepts_rendered_candidate_record() -> None:
    profile = ComprehensiveCvProfile.model_validate(
        {
            "personal_info": {
                "firstname": "Jane",
                "lastname": "Doe",
                "email": "jane@example.com",
                "note": "Senior backend engineer with Python and distributed systems experience.",
            },
            "professional_experience": {
                "primary_designation": "Senior Backend Engineer",
                "work": [],
                "projects": [],
            },
            "education_skills": {
                "skills": ["Python", "FastAPI"],
            },
            "extraction_notes": [],
        }
    )
    markdown = render_cv_markdown(
        profile,
        candidate_id="candidate-123",
        source_file="resume.pdf",
    )

    passed, payload = _build_markdown_guardrail(
        candidate_id="candidate-123",
        source_file="resume.pdf",
    )(DummyTaskOutput(raw=markdown))

    assert passed is True
    assert payload == markdown


def test_markdown_guardrail_rejects_missing_required_sections() -> None:
    markdown = """---
record_type: candidate_resume
candidate_id: "candidate-123"
source_file: "resume.pdf"
---

# Jane Doe

## Contact
"""

    passed, payload = _build_markdown_guardrail(
        candidate_id="candidate-123",
        source_file="resume.pdf",
    )(DummyTaskOutput(raw=markdown))

    assert passed is False
    assert "Missing required section heading" in payload
