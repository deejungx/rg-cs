"""Structured data contracts used by the CV extraction pipeline.

The field descriptions are intentionally explicit: CrewAI exposes this schema to
the LLM, so these descriptions are part of the extraction instructions as well as
the runtime validation contract.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class CvBaseModel(BaseModel):
    """Common validation behavior for extracted CV data."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DateObject(CvBaseModel):
    """A resume date normalized without inventing missing precision."""

    year: int = Field(
        description="Four-digit calendar year explicitly stated in the CV."
    )
    month: int | None = Field(
        default=None,
        ge=1,
        le=12,
        description="Calendar month from 1 to 12, or null when only a year is stated.",
    )


class Industry(str, Enum):
    """Closed set used for consistent candidate and employer classification."""

    TECHNOLOGY_SOFTWARE = "Technology/Software"
    HEALTHCARE_MEDICAL = "Healthcare/Medical"
    FINANCE_BANKING = "Finance/Banking"
    EDUCATION_ACADEMIA = "Education/Academia"
    MARKETING_ADVERTISING = "Marketing/Advertising"
    SALES_BUSINESS_DEVELOPMENT = "Sales/Business Development"
    HUMAN_RESOURCES = "Human Resources"
    OPERATIONS_LOGISTICS = "Operations/Logistics"
    ENGINEERING_MANUFACTURING = "Engineering/Manufacturing"
    LEGAL_LAW = "Legal/Law"
    CONSULTING = "Consulting"
    MEDIA_COMMUNICATIONS = "Media/Communications"
    RETAIL_ECOMMERCE = "Retail/E-commerce"
    REAL_ESTATE = "Real Estate"
    GOVERNMENT_PUBLIC_SECTOR = "Government/Public Sector"
    NON_PROFIT_NGO = "Non-profit/NGO"
    HOSPITALITY_TOURISM = "Hospitality/Tourism"
    TRANSPORTATION = "Transportation"
    ENERGY_UTILITIES = "Energy/Utilities"
    AGRICULTURE_FOOD = "Agriculture/Food"
    ARTS_ENTERTAINMENT = "Arts/Entertainment"
    SPORTS_FITNESS = "Sports/Fitness"
    OTHER = "Other"


class PersonalLink(CvBaseModel):
    name: str = Field(
        default="",
        description="Link label such as LinkedIn, GitHub, Portfolio, or Personal Website.",
    )
    url: str = Field(
        default="", description="Complete URL exactly as supplied in the CV."
    )


class PersonalInfo(CvBaseModel):
    date_of_birth: DateObject | None = Field(
        default=None,
        description="Date of birth only when explicitly stated; never derive it from age or education.",
    )
    firstname: str = Field(
        default="", description="Candidate's given name, excluding honorifics."
    )
    lastname: str = Field(
        default="", description="Candidate's family name or remaining surname(s)."
    )
    email: str = Field(
        default="", description="Primary email address exactly as written."
    )
    phone: str = Field(
        default="",
        description="Primary phone number, preserving an explicitly supplied country code.",
    )
    gender: str = Field(
        default="",
        description="Gender only when directly stated; do not infer it from name, title, or pronouns.",
    )
    address: str = Field(
        default="",
        description="Candidate location or address, limited to the detail present in the CV.",
    )
    two_wheeler: bool | None = Field(
        default=None,
        description="True or false only when two-wheeler ownership/ability is stated; otherwise null.",
    )
    driving_license: bool | None = Field(
        default=None,
        description="True or false only when driving-license status is stated; otherwise null.",
    )
    personal_links: list[PersonalLink] = Field(
        default_factory=list,
        description="All professional, portfolio, repository, and personal-site links in source order.",
    )
    personal_statement: str = Field(
        default="",
        description="Candidate-authored summary, objective, or profile, lightly cleaned but not invented.",
    )
    note: str = Field(
        default="",
        description="A concise generated profile summary grounded only in extracted experience and skills.",
    )


class WorkExperience(CvBaseModel):
    organization_name: str = Field(
        default="", description="Employer or organization name."
    )
    designations: list[str] = Field(
        default_factory=list,
        description="All job titles held at this organization, ordered most recent first.",
    )
    industry: Industry = Field(
        default=Industry.OTHER,
        description="Best matching employer industry from the closed Industry enum.",
    )
    key_responsibilities: list[str] = Field(
        default_factory=list,
        description="Distinct responsibilities and achievements supported by this work entry.",
    )
    still_working: bool | None = Field(
        default=None,
        description="True for Present/Current, false for explicitly ended work, null if unclear.",
    )
    start: DateObject | None = Field(
        default=None, description="Employment start month/year, if stated."
    )
    end: DateObject | None = Field(
        default=None,
        description="Employment end month/year; null for current work or when no end is stated.",
    )
    tools: list[str] = Field(
        default_factory=list,
        description="Technologies, software, platforms, and methods explicitly tied to this work entry.",
    )


class Project(CvBaseModel):
    title: str = Field(
        default="", description="Project name or a short source-grounded identifier."
    )
    projectUrl: str = (
        Field(  # noqa: N815 - retained for compatibility with the existing CV contract
            default="",
            description="Project or repository URL, when supplied.",
        )
    )
    tools: list[str] = Field(
        default_factory=list,
        description="Technologies and methods explicitly associated with the project.",
    )
    summary: str = Field(
        default="",
        description="Concise source-grounded description of the project's purpose and candidate contribution.",
    )
    highlights: list[str] = Field(
        default_factory=list,
        description="Notable outcomes or achievements; preserve metrics exactly and never manufacture them.",
    )


class ProfessionalExperience(CvBaseModel):
    primary_industry: Industry = Field(
        default=Industry.OTHER,
        description="Industry best supported by the candidate's overall work history.",
    )
    primary_designation: str = Field(
        default="",
        description="Most recent or most representative professional title supported by the CV.",
    )
    work: list[WorkExperience] = Field(
        default_factory=list,
        description="Paid, volunteer, and internship experience only, ordered most recent first.",
    )
    projects: list[Project] = Field(
        default_factory=list,
        description="Academic, personal, research, freelance, and professional projects described as projects.",
    )


class Education(CvBaseModel):
    institution_name: str = Field(
        default="", description="School, college, university, or institution name."
    )
    institution_address: str = Field(
        default="", description="Institution location only when stated."
    )
    course_name: str = Field(
        default="",
        description="Degree, qualification, or course name and field of study.",
    )
    grade: str = Field(
        default="",
        description="Grade, GPA, classification, or percentage exactly as stated.",
    )
    still_studying: bool | None = Field(
        default=None,
        description="True for ongoing study, false for completed study, null if status is unclear.",
    )
    start: DateObject | None = Field(
        default=None, description="Study start month/year, if stated."
    )
    end: DateObject | None = Field(
        default=None,
        description="Actual or expected completion month/year, if stated.",
    )


class Training(CvBaseModel):
    institute_name: str = Field(
        default="", description="Training provider or certification issuer."
    )
    course_name: str = Field(
        default="", description="Training, workshop, license, or certification title."
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Skills and technologies explicitly covered by the training or certification.",
    )
    start: DateObject | None = Field(
        default=None, description="Training start month/year, if stated."
    )
    end: DateObject | None = Field(
        default=None,
        description="Completion, award, or expiry month/year when supplied by the CV.",
    )


class EducationSkills(CvBaseModel):
    education_qualification: str = Field(
        default="",
        description="Highest completed academic qualification; use an ongoing qualification only if none is completed.",
    )
    education: list[Education] = Field(
        default_factory=list,
        description="Education entries ordered by highest/recent qualification first.",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Deduplicated technical, domain, language, and soft skills explicitly evidenced in the CV.",
    )
    training: list[Training] = Field(
        default_factory=list,
        description="Certifications, licenses, workshops, and formal training in source order.",
    )


class ComprehensiveCvProfile(CvBaseModel):
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    professional_experience: ProfessionalExperience = Field(
        default_factory=ProfessionalExperience
    )
    education_skills: EducationSkills = Field(default_factory=EducationSkills)
    extraction_notes: list[str] = Field(
        default_factory=list,
        description="Only material ambiguities, contradictions, unreadable text, or truncation affecting extraction.",
    )


class ResumeValidationResult(CvBaseModel):
    is_resume: bool = Field(
        default=False,
        description="Whether the document is predominantly a CV or resume.",
    )
    reason: str = Field(
        default="", description="Brief evidence-based reason for the classification."
    )


class DocumentParseResult(CvBaseModel):
    text: str = ""
    parser: str = ""
    file_type: str = ""
    is_image_based: bool = False
    redaction_applied: bool = False
    _raw_text: str = PrivateAttr(default="")

    @property
    def source_text(self) -> str:
        return self._raw_text or self.text

    def set_source_text(self, value: str) -> None:
        self._raw_text = value


class CandidateArtifacts(CvBaseModel):
    candidate_id: str
    upload_path: str
    structured_markdown_path: str
    structured_json_path: str
    trace_path: str


class CvExtractionResponse(CvBaseModel):
    candidate_id: str
    validation: ResumeValidationResult
    parsed: DocumentParseResult
    structured_profile: ComprehensiveCvProfile | None = None
    artifacts: CandidateArtifacts
