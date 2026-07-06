def test_cv_matching_analyze_returns_structured_response(client) -> None:
    payload = {
        "cv_data": {
            "id": "candidate-1",
            "firstname": "Jane",
            "lastname": "Doe",
            "designation": "Frontend Developer",
            "designations": ["Frontend Developer", "UI Engineer"],
            "address": "Lalitpur",
            "skills": ["React", "TypeScript", "Figma", "HTML", "CSS"],
            "education_qualification": "Bachelors in Computer Science",
            "salary_expectation": {"min": 70000, "max": 90000, "currency": "NPR"},
            "works": [
                {
                    "organization_name": "Acme",
                    "industry": "Technology",
                    "position": "Frontend Developer",
                    "still_working": False,
                    "start": {"year": 2021, "month": 1},
                    "end": {"year": 2023, "month": 12},
                    "key_responsibilities": ["Built React interfaces", "Worked with Figma"],
                    "tools": ["React", "TypeScript"],
                }
            ],
        },
        "vacancy_data": {
            "id": "vacancy-1",
            "title": "Frontend Developer",
            "company_name": "Example Co",
            "company_industry": "Technology",
            "location": "Kathmandu",
            "work_approach": ["Onsite"],
            "employment_type": ["Full Time"],
            "skills_required": ["React", "TypeScript", "Next.js"],
            "education_level": "Bachelor's degree",
            "experience_level": {"min": 2, "max": 4, "level": "Mid"},
            "offered_salary": {"min": 60000, "max": 95000, "currency": "NPR"},
        },
    }

    response = client.post("/api/cv-matching/analyze", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["candidate_id"] == "candidate-1"
    assert body["meta"]["vacancy_id"] == "vacancy-1"
    assert body["candidate_snapshot"]["full_name"] == "Jane Doe"
    assert body["jd_match_overview"]["header"]["jd_title"] == "Frontend Developer"
    assert body["jd_match_overview"]["sections"]["skills"]["matched_skills"] == [
        "React",
        "TypeScript",
    ]
    assert "Next.js" in body["jd_match_overview"]["sections"]["skills"]["missing_or_weak_skills"]
    assert len(body["jd_match_overview"]["criteria_grid"]["rows"]) == 9
