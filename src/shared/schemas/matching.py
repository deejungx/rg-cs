"""Structured contracts for CV-to-vacancy matching."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MatchingBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SalaryRange(MatchingBaseModel):
    min: float | None = None
    max: float | None = None
    currency: str = "NPR"


class DateModel(MatchingBaseModel):
    year: int = Field(..., ge=1900, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)


class WorkExperience(MatchingBaseModel):
    organization_name: str = ""
    industry: str = ""
    position: str = ""
    still_working: bool | None = None
    start: DateModel | None = None
    end: DateModel | None = None
    key_responsibilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class EducationItem(MatchingBaseModel):
    title: str = ""
    institution_name: str = ""
    institution_address: str = ""
    still_studying: bool | None = None
    start: DateModel | None = None
    end: DateModel | None = None


class CVData(MatchingBaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    id: str
    firstname: str = ""
    lastname: str = ""
    full_name: str = ""
    email: str | None = None
    phone: str = ""
    address: str = ""
    designation: str = ""
    designations: list[str] = Field(default_factory=list)
    industry: str = ""
    industries: list[str] = Field(default_factory=list)
    education_qualification: str = ""
    education: list[EducationItem] = Field(default_factory=list)
    experience: str = ""
    works: list[WorkExperience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    about_me: str = ""
    current_status: str = ""
    gender: str = ""
    two_wheeler: bool | None = None
    driving_license: bool | None = None
    note: str = ""
    salary_expectation: SalaryRange | None = None

    @model_validator(mode="after")
    def populate_full_name(self) -> "CVData":
        if not self.full_name:
            self.full_name = " ".join(
                part for part in (self.firstname, self.lastname) if part
            )
        return self


class ExperienceLevel(MatchingBaseModel):
    min: int | None = None
    max: int | None = None
    level: str = ""


class VacancyData(MatchingBaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    id: str
    title: str
    description: str = ""
    category: str = ""
    company_name: str = ""
    company_industry: str = ""
    education_level: str = ""
    skills_required: list[str] = Field(default_factory=list)
    key_responsibilities: list[str] | str | None = None
    employment_type: list[str] = Field(default_factory=list)
    work_approach: list[str] = Field(default_factory=list)
    location: str = ""
    experience_required: str | int | None = None
    experience_level: ExperienceLevel | None = None
    offered_salary: SalaryRange | None = None
    salary_type: str = ""
    gender_preferred: str = ""
    vehicle_required: bool | None = None
    job_tags: list[str] = Field(default_factory=list)


class CVMatchingRequest(MatchingBaseModel):
    cv_data: CVData
    vacancy_data: VacancyData


MatchLabel = Literal["match", "partial", "gap", "major_gap", "mismatch", "missing"]
SeverityLabel = Literal["good", "warning", "bad"]
OtherFactorSeverity = Literal["good", "neutral", "bad", "missing"]
FitLevel = Literal["excellent", "good", "partial", "weak", "not_recommended"]


class ResponseError(MatchingBaseModel):
    code: str
    message: str


class MatchMeta(MatchingBaseModel):
    analysis_id: str
    schema_version: Literal["1.0"] = "1.0"
    created_at: str
    candidate_id: str
    vacancy_id: str
    errors: list[ResponseError] = Field(default_factory=list)


class SalaryRangeResponse(MatchingBaseModel):
    min: float | None = None
    max: float | None = None
    currency: str = "NPR"


class CandidateSnapshot(MatchingBaseModel):
    full_name: str
    work_status: str = ""
    phone: str = ""
    email: str | None = None
    designation: str = ""
    salary_expectation: SalaryRangeResponse | None = None


class MatchBadge(MatchingBaseModel):
    percent: int = Field(..., ge=0, le=100)
    label: MatchLabel
    severity: SeverityLabel


class Pill(MatchingBaseModel):
    text: str
    severity: SeverityLabel


class CompanyLine(MatchingBaseModel):
    company_name: str = ""
    location: str = ""
    employment_type_display: str = ""
    work_approach_display: str = ""


class Header(MatchingBaseModel):
    jd_title: str
    company_line: CompanyLine | None = None
    overall_match: MatchBadge
    pills: list[Pill] = Field(default_factory=list)


class Scorecard(MatchingBaseModel):
    key: str
    title: str
    match: MatchBadge


class Insight(MatchingBaseModel):
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class ExperienceJobRequirement(MatchingBaseModel):
    headline: str
    experience_level: str = ""


class CandidateProfile(MatchingBaseModel):
    headline: str
    detail: str = ""


class ExperienceSection(MatchingBaseModel):
    match: MatchBadge
    job_requirement: ExperienceJobRequirement
    candidate_profile: CandidateProfile
    insight: Insight


class DesignationRoleSection(MatchingBaseModel):
    match: MatchBadge
    job_title_options: list[str] = Field(default_factory=list)
    candidate_titles: list[str] = Field(default_factory=list)
    insight: Insight


class SkillsCoverage(MatchingBaseModel):
    overlap_percent: int = Field(..., ge=0, le=100)
    notes: str = ""


class SkillsSection(MatchingBaseModel):
    match: MatchBadge
    matched_skills: list[str] = Field(default_factory=list)
    missing_or_weak_skills: list[str] = Field(default_factory=list)
    bonus_skills: list[str] = Field(default_factory=list)
    insight: Insight
    coverage: SkillsCoverage


class OtherFactorItem(MatchingBaseModel):
    key: Literal["education", "location", "salary", "gender"]
    jd_preference: str
    candidate_value: str
    label: Literal["match", "partial", "mismatch", "missing"]
    severity: OtherFactorSeverity


class OtherFactorsSection(MatchingBaseModel):
    items: list[OtherFactorItem] = Field(default_factory=list)


class OverallAIAnalysis(MatchingBaseModel):
    headline: str
    overall_summary: str
    overall_fit_level: FitLevel
    key_strengths: list[str] = Field(default_factory=list)
    key_gaps: list[str] = Field(default_factory=list)
    best_fit_roles: list[str] = Field(default_factory=list)
    recommended_interview_focus: list[str] = Field(default_factory=list)
    ai_recommendation: str
    ideal_next_step: str


class CriteriaRow(MatchingBaseModel):
    criterion: str
    jd_requirement: str | None = None
    cv_summary: str | None = None
    label: MatchLabel
    status_note: str
    score: int | None = Field(default=None, ge=0, le=100)


class CriteriaGrid(MatchingBaseModel):
    legend: list[MatchLabel] = Field(
        default_factory=lambda: [
            "match",
            "partial",
            "gap",
            "major_gap",
            "mismatch",
            "missing",
        ]
    )
    rows: list[CriteriaRow] = Field(default_factory=list)


class Sections(MatchingBaseModel):
    experience: ExperienceSection
    designation_role: DesignationRoleSection
    skills: SkillsSection
    other_factors: OtherFactorsSection | None = None
    overall_ai_analysis: OverallAIAnalysis


class JDMatchOverview(MatchingBaseModel):
    header: Header
    scorecards: list[Scorecard] = Field(default_factory=list)
    sections: Sections
    criteria_grid: CriteriaGrid


class CVMatchingResponse(MatchingBaseModel):
    meta: MatchMeta
    candidate_snapshot: CandidateSnapshot
    jd_match_overview: JDMatchOverview


class MatchScore(MatchingBaseModel):
    percent: int = Field(..., ge=0, le=100)
    label: MatchLabel
    severity: SeverityLabel


class InsightOutput(MatchingBaseModel):
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class ExperienceMatchOutput(MatchingBaseModel):
    match: MatchScore
    insight: InsightOutput
    status_note: str


class DesignationMatchOutput(MatchingBaseModel):
    match: MatchScore
    insight: InsightOutput
    status_note: str


class DomainKnowledgeOutput(MatchingBaseModel):
    match: MatchScore
    insight: InsightOutput
    status_note: str


class SkillsCoverageOutput(MatchingBaseModel):
    overlap_percent: int = Field(..., ge=0, le=100)
    notes: str


class SkillsMatchOutput(MatchingBaseModel):
    match: MatchScore
    matched_skills: list[str] = Field(default_factory=list)
    missing_or_weak_skills: list[str] = Field(default_factory=list)
    bonus_skills: list[str] = Field(default_factory=list)
    insight: InsightOutput
    coverage: SkillsCoverageOutput
    status: MatchLabel
    status_note: str


class OtherFactorItemOutput(MatchingBaseModel):
    key: Literal["education", "location", "salary", "gender"]
    jd_preference: str
    candidate_value: str
    status: Literal["match", "partial", "mismatch", "missing"]
    severity: OtherFactorSeverity


class OtherFactorsOutput(MatchingBaseModel):
    items: list[OtherFactorItemOutput] = Field(default_factory=list)


class MatchAnalystOutput(MatchingBaseModel):
    experience: ExperienceMatchOutput
    designation_role: DesignationMatchOutput
    domain_knowledge: DomainKnowledgeOutput
    skills: SkillsMatchOutput
    other_factors: OtherFactorsOutput


class SummaryPillOutput(MatchingBaseModel):
    text: str
    severity: SeverityLabel


class MatchSummaryOutput(MatchingBaseModel):
    headline: str
    overall_summary: str
    overall_score: int = Field(..., ge=0, le=100)
    overall_fit_level: FitLevel
    key_strengths: list[str] = Field(default_factory=list, min_length=3, max_length=5)
    key_gaps: list[str] = Field(default_factory=list, min_length=1, max_length=5)
    best_fit_roles: list[str] = Field(default_factory=list, min_length=1, max_length=3)
    recommended_interview_focus: list[str] = Field(
        default_factory=list, min_length=2, max_length=5
    )
    ai_recommendation: str
    ideal_next_step: str
    pills: list[SummaryPillOutput] = Field(default_factory=list, max_length=2)


class LocationAssessment(MatchingBaseModel):
    candidate_location: str = ""
    vacancy_location: str = ""
    normalized_candidate_location: str = ""
    normalized_vacancy_location: str = ""
    work_approach: list[str] = Field(default_factory=list)
    nearby_match: bool = False
    exact_match: bool = False
    candidate_has_transport: bool = False
    status: Literal["match", "partial", "mismatch", "missing"]
    status_note: str


class SalaryAssessment(MatchingBaseModel):
    candidate_min: float | None = None
    candidate_max: float | None = None
    vacancy_min: float | None = None
    vacancy_max: float | None = None
    status: Literal["match", "partial", "mismatch", "missing"]
    status_note: str


class MatchingFacts(MatchingBaseModel):
    candidate_experience_months: int = 0
    candidate_experience_years: float = 0.0
    vacancy_min_experience_years: int | None = None
    vacancy_max_experience_years: int | None = None
    matched_skill_count: int = 0
    vacancy_skill_count: int = 0
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    candidate_titles: list[str] = Field(default_factory=list)
    vacancy_titles: list[str] = Field(default_factory=list)
    title_overlap: list[str] = Field(default_factory=list)
    candidate_industries: list[str] = Field(default_factory=list)
    vacancy_industry: str = ""
    location_assessment: LocationAssessment = Field(default_factory=LocationAssessment)
    salary_assessment: SalaryAssessment = Field(default_factory=SalaryAssessment)


class MatchingContext(MatchingBaseModel):
    cv_data: CVData
    vacancy_data: VacancyData
    facts: MatchingFacts
    evidence: dict[str, Any] = Field(default_factory=dict)
