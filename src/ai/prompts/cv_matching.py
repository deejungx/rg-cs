EXP_DESIGNATION_ANALYSIS_PROMPT = """Analyze the candidate's work experience and designation against the vacancy requirements.

# Candidate Information

Work experience:
{candidate_works_json}

Current designation:
{candidate_designation}

All designations:
{candidate_designations_json}

# Vacancy Requirements

{vacancy_json}

Task:
- Evaluate experience depth, recency, and role relevance.
- Evaluate whether candidate titles/designations align with the vacancy title and expected role.
- Stay grounded in the supplied data and do not infer missing facts.
- Keep text concise and recruiter-friendly.

Return only a valid ExperienceAndDesignationAnalysis JSON object.
"""


EXP_DESIGNATION_ANALYSIS_EXPECTED_OUTPUT = """One ExperienceAndDesignationAnalysis object containing:
- experience
- designation_role
"""


SKILLS_ANALYSIS_PROMPT = """Analyze the candidate's skillset in relation to the vacancy requirements.

# Candidate Information

Work experience for evidence of skills:
{candidate_works_json}

Candidate skills:
{candidate_skills_json}

# Vacancy Requirements

{vacancy_json}

Task:
1. Extract vacancy-mentioned skills from skills_required.
2. Compare against the candidate skills list and explicit work-experience evidence.
3. Classify skills into:
- matched_skills: vacancy skills clearly present in candidate skills or work evidence.
- missing_or_weak_skills: vacancy skills not explicitly mentioned.
- bonus_skills: candidate skills not required by the vacancy but relevant to the role.

Rules:
- Use vacancy skill wording as-is for matched_skills and missing_or_weak_skills.
- Do not invent skills.
- Treat weak implication as missing_or_weak_skills.
- Compute coverage.overlap_percent as round(count(matched_skills) / max(1, count(vacancy skills_required)) * 100).
- skills.status must equal skills.match.label.
- Keep insight.text to 1-2 concise recruiter-friendly sentences.

Return only a valid SkillsMatchOutput JSON object.
"""


SKILLS_ANALYSIS_EXPECTED_OUTPUT = """One SkillsMatchOutput object containing matched skills, missing or weak skills, bonus skills, coverage, insight, status, and match score."""


OTHER_FACTORS_ANALYSIS_PROMPT = """Analyze non-skill, non-experience match factors by comparing the candidate CV with the vacancy requirements.

# Candidate Information

Education:
{candidate_education}

Location:
{candidate_location}

Salary expectation:
{candidate_salary_json}

Gender:
{candidate_gender}

# Vacancy Requirements

{vacancy_json}

Task:
Evaluate only factors explicitly mentioned in vacancy data:
- education
- location
- salary
- gender

Rules:
- If a factor is not mentioned in vacancy data, do not include it.
- If vacancy mentions a factor but candidate value is missing, set candidate_value to "Not specified" and status to "missing".
- Do not infer or guess missing CV values.
- status must be one of: match, partial, mismatch, missing.
- severity must map as: match -> good, partial -> neutral, mismatch -> bad, missing -> missing.
- Keep text concise and recruiter-friendly.

Return only a valid OtherFactorsOutput JSON object.
"""


OTHER_FACTORS_ANALYSIS_EXPECTED_OUTPUT = """One OtherFactorsOutput object with zero or more education, location, salary, or gender items."""


CRITERIA_GRID_ANALYSIS_PROMPT = """Generate a criteria grid summarizing the candidate-vacancy match.

# Candidate CV Data

{cv_json}

# Vacancy Data

{vacancy_json}

Task:
Create criteria grid rows using the rules below. Return only the grid output.

Statuses allowed:
match | partial | gap | major_gap | mismatch | missing

General rules:
- Keep jd_requirement, cv_summary, and status_note concise and recruiter-friendly.
- status_note should be very short, preferably under 7 words.

Rows:
1. Core Skills: compare vacancy skills_required and responsibilities against candidate skills and work evidence.
2. Experience Level: compare vacancy experience requirements against candidate work history.
3. Domain Knowledge: compare domain/process knowledge implied by vacancy against candidate skills and responsibilities.
4. Education: generate only status, status_note, and score.
5. Industry Alignment: compare vacancy company_industry/category against candidate industries and work history.
6. Job Title Similarity: generate only status, status_note, and score.
7. Skills Overlap: summarize strongest overlaps and biggest missing skills.
8. Location: compare vacancy work_approach/location against candidate location and transport evidence.
9. Salary Expectation: generate only status and status_note.

Scoring guidance:
- score is 0-100 where required.
- match: 80-100
- partial: 50-79
- gap: 30-49
- major_gap/mismatch: 0-29
- missing: score can be null

Return only a valid CriteriaGridOutput JSON object.
"""


CRITERIA_GRID_ANALYSIS_EXPECTED_OUTPUT = """One CriteriaGridOutput object containing legend and criteria grid rows."""


OVERALL_ANALYSIS_PROMPT = """Generate the final overall AI analysis for a candidate-vacancy match.

Your role is to synthesize insights using only:
- candidate CV data
- vacancy data
- the completed branch analysis results

Do not introduce new facts or assumptions that contradict the provided inputs.

# Candidate CV Data

{cv_json}

# Vacancy Data

{vacancy_json}

# Analysis Results

Experience and designation analysis:
{experience_designation_json}

Skills analysis:
{skills_json}

Other factors analysis:
{other_factors_json}

Criteria grid analysis:
{criteria_grid_json}

Task:
- Write one short decisive headline.
- Write one concise paragraph explaining overall fit, major strengths, and important gaps.
- Give overall_score from 0 to 100.
- Choose overall_fit_level exactly one of: excellent, good, partial, weak, not_recommended.
- List 3 to 5 concrete strengths.
- List the most impactful gaps.
- Suggest 1 to 3 alternative or adjacent best-fit roles.
- List specific interview focus areas.
- Choose ai_recommendation from: Proceed, Proceed with caution, Hold for better role fit, Reject for this role.
- Suggest one concrete ideal_next_step.
- Add up to two short pills, each 3-5 words.

Return only a valid MatchSummaryOutput JSON object.
"""


OVERALL_ANALYSIS_EXPECTED_OUTPUT = """One MatchSummaryOutput object containing final score, fit level, strengths, gaps, recommendation, next step, and pills."""
