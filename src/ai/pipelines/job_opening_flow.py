import json
import re
from html.parser import HTMLParser
from typing import Any
from uuid import uuid4

import httpx
from crewai import Process, Task
from crewai.tools import BaseTool
from pydantic import ValidationError

from app.core.config import settings
from src.ai.integrations.deepeval_crewai import Agent, Crew, LLM, initialize_deepeval
from src.ai.providers import get_model_provider
from src.ai.tracing.phoenix import initialize_phoenix
from src.shared.schemas import (
    AnnotatedJobOpening,
    JobExperienceLevel,
    JobOpeningMetadata,
    JobSalaryRange,
)

IMPORTANT_FIELDS = (
    "title",
    "description",
    "company_name",
    "location",
    "skills_required",
    "employment_type",
    "work_approach",
    "key_responsibilities",
)


class SerperSearchTool(BaseTool):
    name: str = "serper_web_search"
    description: str = "Search the web with Serper for job-opening pages and source context."

    def _run(self, query: str) -> str:
        if not settings.serper_api_key:
            return "Serper search unavailable: SERPER_API_KEY is not configured."
        try:
            response = httpx.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": settings.serper_api_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": 5},
                timeout=10,
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False)
        except Exception as exc:
            return f"Serper search failed: {exc}"


class _MarkdownHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"p", "div", "section", "article", "br", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.parts.append(text + " ")

    def markdown(self) -> str:
        text = "".join(self.parts)
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)


def _build_llm():
    provider = get_model_provider()
    if not provider.uses_live_llm:
        return None
    return LLM(
        model=f"openai/{settings.openai_model}",
        api_key=settings.openai_api_key,
        temperature=settings.default_temperature,
    )


def _fetch_website_markdown(url: str) -> str:
    response = httpx.get(
        url,
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "AutoRecruitBot/0.1"},
    )
    response.raise_for_status()
    parser = _MarkdownHTMLParser()
    parser.feed(response.text)
    return parser.markdown()[:25000]


def _missing_fields(job: AnnotatedJobOpening) -> list[str]:
    missing: list[str] = []
    payload = job.model_dump()
    for field in IMPORTANT_FIELDS:
        value = payload.get(field)
        if value in (None, "", []) or value == {}:
            missing.append(field)
    return missing


def _quality_warnings(job: AnnotatedJobOpening) -> list[str]:
    warnings: list[str] = []
    if len(job.description) < 80:
        warnings.append("description is short")
    if len(job.skills_required) < 2:
        warnings.append("fewer than two required skills extracted")
    if not job.key_responsibilities:
        warnings.append("responsibilities are missing")
    if not job.company_name:
        warnings.append("company name is missing")
    return warnings


def _apply_metadata_quality(
    job: AnnotatedJobOpening,
    *,
    source_type: str,
    source_url: str = "",
) -> AnnotatedJobOpening:
    missing = _missing_fields(job)
    warnings = _quality_warnings(job)
    confidence = max(0.2, min(1.0, 1.0 - (len(missing) * 0.08) - (len(warnings) * 0.05)))
    job.metadata = JobOpeningMetadata(
        source_type=source_type,  # type: ignore[arg-type]
        source_url=source_url,
        missing_fields=missing,
        quality_warnings=warnings,
        confidence=round(confidence, 2),
    )
    return job


def _load_job_output(task_output: object) -> AnnotatedJobOpening:
    pydantic_output = getattr(task_output, "pydantic", None)
    if isinstance(pydantic_output, AnnotatedJobOpening):
        return pydantic_output
    raw = getattr(task_output, "raw", "")
    if isinstance(raw, str):
        return AnnotatedJobOpening.model_validate_json(raw)
    json_dict = getattr(task_output, "json_dict", None)
    if isinstance(json_dict, dict):
        return AnnotatedJobOpening.model_validate(json_dict)
    raise ValueError("CrewAI output could not be parsed as AnnotatedJobOpening.")


def _job_guardrail(task_output: object) -> tuple[bool, Any]:
    try:
        job = _load_job_output(task_output)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return (False, f"Return a valid AnnotatedJobOpening object. {exc}")

    missing = _missing_fields(job)
    warnings = _quality_warnings(job)
    severe_missing = [field for field in missing if field in {"title", "description"}]
    if severe_missing:
        return (
            False,
            f"Critical fields missing: {', '.join(severe_missing)}. Extract them or state supported fallback text.",
        )
    if len(warnings) >= 4:
        return (False, "The job opening is too sparse. Extract more hiring-relevant details.")
    return (True, job)


def _normalize_employment(text: str) -> list[str]:
    lowered = text.lower()
    values = []
    if "full" in lowered:
        values.append("full_time")
    if "part" in lowered:
        values.append("part_time")
    if "project" in lowered:
        values.append("project_based")
    if "contract" in lowered:
        values.append("contract")
    if "intern" in lowered:
        values.append("internship")
    return values


def _fallback_extract(text: str, *, source_type: str, source_url: str = "") -> AnnotatedJobOpening:
    stripped = text.strip()
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            data.setdefault("id", str(uuid4()))
            data["metadata"] = {
                "source_type": source_type,
                "source_url": source_url,
                "missing_fields": [],
                "quality_warnings": [],
                "confidence": 0.75,
            }
            job = AnnotatedJobOpening.model_validate(data)
            return _apply_metadata_quality(job, source_type=source_type, source_url=source_url)
    except (json.JSONDecodeError, ValidationError):
        pass

    lines = [line.strip(" -•\t") for line in stripped.splitlines() if line.strip()]
    title = lines[0][:120] if lines else "Untitled job opening"
    skills = sorted(set(re.findall(r"\b(?:React|Python|FastAPI|Django|UI/UX|Figma|Adobe Suite|JavaScript|TypeScript|SQL|Redis|Qdrant)\b", stripped, flags=re.I)))
    salary_numbers = [float(value) for value in re.findall(r"\b\d{4,6}\b", stripped)]
    salary = None
    if salary_numbers:
        salary = JobSalaryRange(min=min(salary_numbers), max=max(salary_numbers))
    experience_numbers = [int(value) for value in re.findall(r"\b(\d+)\+?\s*(?:years?|yrs?)", stripped, flags=re.I)]
    experience = None
    if experience_numbers:
        experience = JobExperienceLevel(min=min(experience_numbers), max=max(experience_numbers), level="mid")
    location_match = re.search(r"(Kathmandu|Lalitpur|Bhaktapur|Pokhara|Remote)", stripped, flags=re.I)
    company_match = re.search(r"(?:company|organization|employer)\s*[:\-]\s*([^\n]+)", stripped, flags=re.I)
    job = AnnotatedJobOpening(
        id=str(uuid4()),
        title=title,
        description=" ".join(lines[:8])[:1600],
        employment_type=_normalize_employment(stripped),
        work_approach=["remote"] if "remote" in stripped.lower() else ["onsite"] if "onsite" in stripped.lower() or "office" in stripped.lower() else [],
        offered_salary=salary,
        key_responsibilities="\n".join(f"- {line}" for line in lines[1:8]),
        location=location_match.group(1) if location_match else "",
        skills_required=skills,
        experience_level=experience,
        company_name=company_match.group(1).strip() if company_match else "",
        category="",
        metadata=JobOpeningMetadata(source_type=source_type, source_url=source_url, confidence=0.4),
    )
    return _apply_metadata_quality(job, source_type=source_type, source_url=source_url)


def render_job_opening_markdown(job: AnnotatedJobOpening) -> str:
    skills = "\n".join(f"- {skill}" for skill in job.skills_required) or "- Not specified"
    tags = ", ".join(job.job_tags) or "Not specified"
    salary = "Not specified"
    if job.offered_salary:
        salary = f"{job.offered_salary.currency} {job.offered_salary.min or ''}-{job.offered_salary.max or ''}".strip()
    return (
        f"# {job.title}\n\n"
        f"**Company:** {job.company_name or 'Not specified'}\n\n"
        f"**Location:** {job.location or 'Not specified'}\n\n"
        f"**Employment type:** {', '.join(job.employment_type) or 'Not specified'}\n\n"
        f"**Work approach:** {', '.join(job.work_approach) or 'Not specified'}\n\n"
        f"**Salary:** {salary}\n\n"
        f"**Tags:** {tags}\n\n"
        "## Description\n\n"
        f"{job.description or 'No description extracted.'}\n\n"
        "## Responsibilities\n\n"
        f"{job.key_responsibilities or 'Not specified'}\n\n"
        "## Skills Required\n\n"
        f"{skills}\n\n"
        "## Company\n\n"
        f"{job.about_company or job.company_industry or 'Not specified'}\n"
    )


def run_job_opening_flow(*, source_type: str, content: str) -> tuple[AnnotatedJobOpening, str]:
    initialize_deepeval()
    initialize_phoenix()
    llm = _build_llm()
    source_url = content.strip() if source_type == "website" else ""

    if source_type == "website":
        try:
            source_text = _fetch_website_markdown(source_url)
        except Exception:
            source_text = content
    else:
        source_text = content

    if llm is None:
        job = _fallback_extract(source_text, source_type=source_type, source_url=source_url)
        return job, render_job_opening_markdown(job)

    extractor = Agent(
        role="Recruitment Job Opening Curator",
        goal="Create complete, source-grounded structured job-opening records for recruiter workflows.",
        backstory=(
            "You specialize in normalizing messy job posts into precise hiring data. "
            "You preserve only source-supported facts and explicitly leave missing fields empty."
        ),
        llm=llm,
        tools=[SerperSearchTool()] if source_type == "website" else [],
        max_iter=8,
        max_execution_time=120,
        allow_delegation=False,
        verbose=False,
    )

    description = (
        "Extract a job opening from the source below into the AnnotatedJobOpening schema. "
        "If the source is a website, use Serper search only to locate or confirm relevant source context; "
        "ignore navigation, ads, unrelated jobs, cookie banners, and boilerplate. "
        "Normalize employment_type and work_approach to snake_case values. "
        "Use Markdown bullets for key_responsibilities. "
        "Set metadata.source_type, metadata.source_url, and leave metadata.missing_fields empty for now; "
        "the application will fill final metadata after guardrail checks.\n\n"
        f"Source type: {source_type}\nSource URL: {source_url}\n\nSource content:\n---\n{source_text[:22000]}\n---"
    )
    task = Task(
        description=description,
        expected_output=(
            "A valid AnnotatedJobOpening object with complete source-grounded job details. "
            "Critical fields title and description must be populated."
        ),
        agent=extractor,
        output_pydantic=AnnotatedJobOpening,
        guardrail=_job_guardrail,
        guardrail_max_retries=2,
    )
    crew = Crew(agents=[extractor], tasks=[task], process=Process.sequential, verbose=False)
    crew.kickoff()
    job = _load_job_output(task.output)
    job = _apply_metadata_quality(job, source_type=source_type, source_url=source_url)
    return job, render_job_opening_markdown(job)
