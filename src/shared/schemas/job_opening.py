from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobOpeningBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class JobSalaryRange(JobOpeningBaseModel):
    min: float | None = Field(
        default=None,
        description="Minimum offered salary exactly stated in the source, without currency symbols.",
    )
    max: float | None = Field(
        default=None,
        description="Maximum offered salary exactly stated in the source, without currency symbols.",
    )
    currency: str = Field(
        default="NPR",
        description="Salary currency code; default to NPR for Nepal-focused postings when not stated.",
    )


class JobExperienceLevel(JobOpeningBaseModel):
    min: int | None = Field(
        default=None,
        ge=0,
        description="Minimum years of experience required, if stated.",
    )
    max: int | None = Field(
        default=None,
        ge=0,
        description="Maximum years of experience required, if stated.",
    )
    level: str = Field(
        default="",
        description="Normalized seniority label such as intern, junior, mid, senior, lead, or empty if unclear.",
    )


class JobOpeningMetadata(JobOpeningBaseModel):
    source_type: Literal["pasted_text", "website"] = Field(
        description="Input channel used to create the job opening."
    )
    source_url: str = Field(default="", description="Website URL when source_type is website.")
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Important job-opening fields not found in the source.",
    )
    quality_warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking quality issues found by the final guardrail.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Extraction confidence from 0 to 1.",
    )


class AnnotatedJobOpening(JobOpeningBaseModel):
    id: str = Field(description="Stable UUID for the curated job opening.")
    title: str = Field(description="Public job title exactly supported by the source.")
    description: str = Field(
        default="",
        description="Concise cleaned role description focused on hiring-relevant details.",
    )
    education_level: str = Field(
        default="",
        description="Normalized education level such as see, high_school, bachelor, master, phd, or empty if missing.",
    )
    employment_type: list[str] = Field(
        default_factory=list,
        description="Normalized employment types, e.g. full_time, part_time, contract, project_based, internship.",
    )
    work_approach: list[str] = Field(
        default_factory=list,
        description="Normalized work arrangement values, e.g. onsite, remote, hybrid.",
    )
    offered_salary: JobSalaryRange | None = Field(
        default=None,
        description="Offered salary range when stated.",
    )
    experience_required: str | int | None = Field(
        default=None,
        description="Raw experience requirement when the source gives a non-normalized phrase.",
    )
    gender_preferred: str = Field(
        default="",
        description="Gender preference only when explicitly stated; never infer.",
    )
    key_responsibilities: str = Field(
        default="",
        description="Clean Markdown bullet list or paragraph of responsibilities from the source.",
    )
    vehicle_required: bool | None = Field(
        default=None,
        description="Whether vehicle ownership is required, only when explicitly stated.",
    )
    location: str = Field(default="", description="Job location exactly supported by the source.")
    openings: int | None = Field(default=None, ge=0, description="Number of openings.")
    salary_type: str = Field(
        default="",
        description="Salary type such as negotiable, fixed, monthly, yearly, or empty if missing.",
    )
    skills_required: list[str] = Field(
        default_factory=list,
        description="Required skills, tools, technologies, or competencies.",
    )
    job_tags: list[str] = Field(
        default_factory=list,
        description="Posting tags or recruiter-facing labels explicitly present in the source.",
    )
    experience_level: JobExperienceLevel | None = Field(
        default=None,
        description="Normalized experience range and seniority level.",
    )
    category: str = Field(default="", description="Job category or functional area.")
    company_name: str = Field(default="", description="Hiring company name.")
    company_size: str = Field(default="", description="Company size range when stated.")
    about_company: str = Field(default="", description="Brief company description from the source.")
    company_industry: str = Field(default="", description="Company industry when stated.")
    metadata: JobOpeningMetadata = Field(
        description="Extraction metadata, missing fields, quality warnings, and confidence."
    )

    @field_validator("employment_type", "work_approach", "skills_required", "job_tags", mode="before")
    @classmethod
    def ensure_list(cls, value: list[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    @field_validator("openings", mode="before")
    @classmethod
    def coerce_openings(cls, value: int | str | None) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class JobOpeningExtractionRequest(JobOpeningBaseModel):
    source_type: Literal["pasted_text", "website"]
    content: str = Field(description="Pasted job text or website URL.")


class JobOpeningExtractionResponse(JobOpeningBaseModel):
    job_opening: AnnotatedJobOpening
    markdown: str
    json_path: str
    markdown_path: str
