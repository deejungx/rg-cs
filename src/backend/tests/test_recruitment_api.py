from crewai import Agent, Task

from app.core.config import settings
from src.ai.pipelines.job_opening_flow import _job_guardrail


def test_job_opening_guardrail_is_accepted_by_crewai_task_validator() -> None:
    agent = Agent(role="validator", goal="validate", backstory="test agent")

    task = Task(
        description="Extract a job opening.",
        expected_output="A valid job opening.",
        agent=agent,
        guardrail=_job_guardrail,
    )

    assert task.guardrail is _job_guardrail


def test_job_opening_status_can_be_updated(client) -> None:
    response = client.post(
        "/api/recruitment/job-openings",
        json={
            "title": "Product Designer",
            "company_name": "Acme",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "active"

    update_response = client.patch(
        f"/api/recruitment/job-openings/{payload['id']}/status",
        json={"status": "inactive"},
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "inactive"
    assert updated["updated_at"] != payload["updated_at"]

    list_response = client.get("/api/recruitment/job-openings")
    assert list_response.status_code == 200
    assert list_response.json()["job_openings"][0]["status"] == "inactive"

    markdown_response = client.get(f"/api/workspace/{payload['markdown_path']}")
    assert markdown_response.status_code == 200
    assert "**Status:** inactive" in markdown_response.json()["content"]

    dashboard_response = client.get("/api/recruitment/dashboard")
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["job_openings_total"] == 1
    assert dashboard["active_job_openings"] == 0


def test_dashboard_counts_structured_candidates_not_raw_uploads(client) -> None:
    resume_dir = settings.uploads_dir / "resumes" / "raw-upload-only"
    resume_dir.mkdir(parents=True)
    (resume_dir / "resume.pdf").write_bytes(b"%PDF-1.4\n")

    dashboard_response = client.get("/api/recruitment/dashboard")

    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["candidates_total"] == 0


def test_job_opening_extraction_from_pasted_json_stores_annotated_artifacts(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "model_provider", "mock")

    response = client.post(
        "/api/recruitment/job-openings/extract",
        json={
            "source_type": "pasted_text",
            "content": """
            {
              "id": "1f341304-9792-40d0-ae4f-bef7b157a565",
              "title": "UI/UX",
              "description": "We are seeking a talented and experienced UI/UX Designer to join our dynamic team in Kathmandu.",
              "education_level": "bachelor",
              "employment_type": ["full_time", "project_based"],
              "work_approach": ["onsite"],
              "offered_salary": {"min": 10000, "max": 70000},
              "experience_required": null,
              "gender_preferred": "female",
              "key_responsibilities": "Design web and mobile interfaces.",
              "vehicle_required": false,
              "location": "Kathmandu",
              "openings": "1",
              "salary_type": "negotiable",
              "skills_required": ["UX or UI design", "Adobe Suite"],
              "job_tags": ["Within Ring Road", "Office based work"],
              "experience_level": {"max": 2, "min": 0, "level": "mid"},
              "category": "UI/UX Designing",
              "company_name": "Edited Rame Dai",
              "company_size": "10-50",
              "about_company": "it's testing company",
              "company_industry": "Accounting"
            }
            """,
        },
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    run_response = client.get(f"/api/recruitment/job-openings/runs/{run_id}")
    assert run_response.status_code == 200
    payload = run_response.json()["result"]
    job = payload["job_opening"]
    assert job["title"] == "UI/UX"
    assert job["metadata"]["source_type"] == "pasted_text"
    assert "title" not in job["metadata"]["missing_fields"]
    assert payload["json_path"].endswith("/job_opening.json")
    assert payload["markdown_path"].endswith("/job_opening.md")

    json_response = client.get(f"/api/workspace/{payload['json_path']}")
    markdown_response = client.get(f"/api/workspace/{payload['markdown_path']}")
    assert json_response.status_code == 200
    assert markdown_response.status_code == 200
    assert "UI/UX" in markdown_response.json()["content"]

    events_response = client.get(f"/api/recruitment/job-openings/runs/{run_id}/events")
    assert events_response.status_code == 200
    assert '"label": "extract_structured_job"' in events_response.text


def test_candidates_endpoint_returns_summarized_workspace_records(client) -> None:
    response = client.post(
        "/api/recruitment/job-openings",
        json={"title": "Placeholder"},
    )
    assert response.status_code == 200

    from app.core.config import settings

    candidate_dir = settings.workspace_dir / "candidates" / "candidate-1"
    candidate_dir.mkdir(parents=True)
    (candidate_dir / "resume.md").write_text("# Jane Doe\n", encoding="utf-8")
    (candidate_dir / "resume_structured.json").write_text(
        """
        {
          "personal_info": {
            "firstname": "Jane",
            "lastname": "Doe",
            "address": "Kathmandu"
          },
          "professional_experience": {
            "primary_designation": "Frontend Engineer",
            "primary_industry": "Technology/Software",
            "work": [{"organization_name": "Acme"}],
            "projects": [{"title": "Hiring Portal"}]
          },
          "education_skills": {
            "education_qualification": "BSc CS",
            "skills": ["React", "TypeScript", "FastAPI", "Redis", "Qdrant"]
          },
          "extraction_notes": []
        }
        """,
        encoding="utf-8",
    )

    candidates_response = client.get("/api/recruitment/candidates")
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()["candidates"]
    assert candidates == [
        {
            "candidate_id": "candidate-1",
            "full_name": "Jane Doe",
            "primary_designation": "Frontend Engineer",
            "primary_industry": "Technology/Software",
            "location": "Kathmandu",
            "education_qualification": "BSc CS",
            "skills": ["React", "TypeScript", "FastAPI", "Redis", "Qdrant"],
            "skill_count": 5,
            "experience_count": 1,
            "project_count": 1,
            "updated_at": candidates[0]["updated_at"],
            "structured_json_path": "candidates/candidate-1/resume_structured.json",
            "structured_markdown_path": "candidates/candidate-1/resume.md",
        }
    ]
