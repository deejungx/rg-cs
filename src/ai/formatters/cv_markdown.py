import json
from calendar import month_abbr

from src.shared.schemas import ComprehensiveCvProfile, DateObject


def _date(value: DateObject | None) -> str:
    if value is None:
        return ""
    if value.month is None:
        return str(value.year)
    return f"{month_abbr[value.month]} {value.year}"


def _date_range(
    start: DateObject | None,
    end: DateObject | None,
    *,
    ongoing: bool | None = None,
) -> str:
    start_text = _date(start)
    end_text = "Present" if ongoing else _date(end)
    if start_text and end_text:
        return f"{start_text} – {end_text}"
    return start_text or end_text or "Not provided"


def _bullet(label: str, value: str) -> str:
    return f"- **{label}:** {value}"


def render_cv_markdown(
    profile: ComprehensiveCvProfile,
    *,
    candidate_id: str,
    source_file: str,
) -> str:
    """Render a complete, predictable Markdown record without adding facts."""

    personal = profile.personal_info
    professional = profile.professional_experience
    education_skills = profile.education_skills
    full_name = " ".join(
        part for part in (personal.firstname, personal.lastname) if part
    )
    title = full_name or "Unnamed Candidate"
    primary_industry = (
        professional.primary_industry.value
        if professional.work or professional.primary_designation
        else "Not provided"
    )

    lines = [
        "---",
        "record_type: candidate_resume",
        f"candidate_id: {json.dumps(candidate_id)}",
        f"source_file: {json.dumps(source_file)}",
        "---",
        "",
        f"# {title}",
        "",
        "> Structured candidate record. Prefer the accompanying JSON for machine processing.",
        "",
        "## At a Glance",
        "",
        _bullet(
            "Primary designation", professional.primary_designation or "Not provided"
        ),
        _bullet("Primary industry", primary_industry),
        _bullet("Location", personal.address or "Not provided"),
        _bullet(
            "Highest qualification",
            education_skills.education_qualification or "Not provided",
        ),
        "",
        "## Contact",
        "",
        _bullet("Email", personal.email or "Not provided"),
        _bullet("Phone", personal.phone or "Not provided"),
    ]

    for link in personal.personal_links:
        if link.url:
            lines.append(_bullet(link.name or "Link", link.url))

    lines.extend(["", "## Profile", ""])
    if personal.note:
        lines.append(personal.note)
    elif personal.personal_statement:
        lines.append(personal.personal_statement)
    else:
        lines.append("Not provided.")

    if personal.personal_statement and personal.personal_statement != personal.note:
        lines.extend(["", "### Candidate Statement", "", personal.personal_statement])

    lines.extend(["", "## Skills", ""])
    if education_skills.skills:
        lines.append(", ".join(education_skills.skills))
    else:
        lines.append("Not provided.")

    lines.extend(["", "## Work Experience", ""])
    if not professional.work:
        lines.append("Not provided.")
    for work in professional.work:
        designation = ", ".join(work.designations) or "Role not provided"
        organization = work.organization_name or "Organization not provided"
        lines.extend(
            [
                f"### {designation} — {organization}",
                "",
                _bullet(
                    "Dates",
                    _date_range(work.start, work.end, ongoing=work.still_working),
                ),
                _bullet("Industry", work.industry.value),
            ]
        )
        if work.tools:
            lines.append(_bullet("Tools", ", ".join(work.tools)))
        if work.key_responsibilities:
            lines.extend(["", "**Responsibilities and achievements**", ""])
            lines.extend(f"- {item}" for item in work.key_responsibilities)
        lines.append("")

    lines.extend(["## Projects", ""])
    if not professional.projects:
        lines.append("Not provided.")
    for project in professional.projects:
        lines.extend([f"### {project.title or 'Untitled Project'}", ""])
        if project.projectUrl:
            lines.append(_bullet("URL", project.projectUrl))
        if project.tools:
            lines.append(_bullet("Tools", ", ".join(project.tools)))
        if project.summary:
            lines.extend(["", project.summary])
        if project.highlights:
            lines.extend(["", "**Highlights**", ""])
            lines.extend(f"- {item}" for item in project.highlights)
        lines.append("")

    lines.extend(["## Education", ""])
    if not education_skills.education:
        lines.append("Not provided.")
    for education in education_skills.education:
        course = education.course_name or "Qualification not provided"
        institution = education.institution_name or "Institution not provided"
        lines.extend(
            [
                f"### {course} — {institution}",
                "",
                _bullet(
                    "Dates",
                    _date_range(education.start, education.end),
                ),
            ]
        )
        if education.still_studying is True:
            lines.append(_bullet("Status", "In progress"))
        if education.institution_address:
            lines.append(_bullet("Location", education.institution_address))
        if education.grade:
            lines.append(_bullet("Grade", education.grade))
        lines.append("")

    lines.extend(["## Training and Certifications", ""])
    if not education_skills.training:
        lines.append("Not provided.")
    for training in education_skills.training:
        title = training.course_name or "Training title not provided"
        provider = training.institute_name or "Provider not provided"
        lines.extend(
            [
                f"### {title} — {provider}",
                "",
                _bullet("Dates", _date_range(training.start, training.end)),
            ]
        )
        if training.skills:
            lines.append(_bullet("Skills", ", ".join(training.skills)))
        lines.append("")

    lines.extend(["## Extraction Notes", ""])
    if profile.extraction_notes:
        lines.extend(f"- {note}" for note in profile.extraction_notes)
    else:
        lines.append("No material extraction issues recorded.")

    return "\n".join(lines).strip() + "\n"
