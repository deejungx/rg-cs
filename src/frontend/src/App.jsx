import React, { useEffect, useMemo, useState } from "react";

const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: "D" },
  { id: "candidates", label: "Candidates", icon: "C" },
  { id: "jobs", label: "Job Openings", icon: "J" },
  { id: "matching", label: "Matching", icon: "M" },
  { id: "settings", label: "Settings", icon: "S" },
];

const extractionSteps = [
  { id: "parse_document", label: "Parse document" },
  { id: "validate_document", label: "Validate resume" },
  { id: "extract_structured_profile", label: "Extract structured JSON" },
  { id: "review_missing_fields", label: "Review missing fields" },
  { id: "curate_structured_markdown", label: "Curate Markdown" },
  { id: "persist_outputs", label: "Persist artifacts" },
];

const matchingSteps = [
  { id: "parse_document", label: "Parse document" },
  { id: "validate_document", label: "Validate resume" },
  { id: "extract_structured_profile", label: "Extract structured JSON" },
  { id: "review_missing_fields", label: "Review missing fields" },
  { id: "curate_structured_markdown", label: "Curate Markdown" },
  { id: "persist_outputs", label: "Persist candidate artifacts" },
  { id: "build_matching_context", label: "Build matching context" },
  { id: "analyze_experience_designation", label: "Experience and designation analysis" },
  { id: "analyze_skills", label: "Skill match analysis" },
  { id: "analyze_other_factors", label: "Other factor analysis" },
  { id: "analyze_criteria_grid", label: "Criteria grid" },
  { id: "analyze_overall_fit", label: "Overall analysis" },
  { id: "assemble_match_results", label: "Assemble results" },
];

const storedCandidateMatchingSteps = [
  { id: "build_matching_context", label: "Build matching context" },
  { id: "analyze_experience_designation", label: "Experience and designation analysis" },
  { id: "analyze_skills", label: "Skill match analysis" },
  { id: "analyze_other_factors", label: "Other factor analysis" },
  { id: "analyze_criteria_grid", label: "Criteria grid" },
  { id: "analyze_overall_fit", label: "Overall analysis" },
  { id: "assemble_match_results", label: "Assemble results" },
];

const jobOpeningTextSteps = [
  { id: "read_pasted_text", label: "Read pasted text" },
  { id: "validate_job_description", label: "Validate job description" },
  { id: "extract_structured_job", label: "Extract structured job" },
  { id: "review_missing_fields", label: "Review missing fields" },
  { id: "persist_job_opening", label: "Persist artifacts" },
];

const jobOpeningWebsiteSteps = [
  { id: "fetch_source_content", label: "Fetch and clean website" },
  { id: "validate_job_description", label: "Validate job description" },
  { id: "extract_structured_job", label: "Extract structured job" },
  { id: "review_missing_fields", label: "Review missing fields" },
  { id: "persist_job_opening", label: "Persist artifacts" },
];

async function parseJson(response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return response.json();
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function formatDate(value) {
  if (!value) {
    return "Not available";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatLatency(ms) {
  if (!Number.isFinite(ms) || ms < 0) {
    return "";
  }
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }
  return `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)}s`;
}

function statusClass(status) {
  if (status === "completed" || status === true || status === "ready" || status === "active") {
    return "status-ok";
  }
  if (status === "failed" || status === false || status === "inactive") {
    return "status-bad";
  }
  return "status-warn";
}

function formatJobStatus(status) {
  return status === "inactive" ? "inactive" : "active";
}

function StatusDot({ value }) {
  return <span className={`status-dot ${statusClass(value)}`} />;
}

function HealthStrip({ health }) {
  const services = health?.services || {};
  const serviceItems = ["redis", "worker", "phoenix", "qdrant", "workspace"];
  return (
    <div className="health-strip">
      <div className="health-brand">
        <span className="brand-mark">AR</span>
        <strong>AutoRecruit Ops</strong>
      </div>
      <div className="health-services">
        {serviceItems.map((service) => (
          <span className="health-chip" key={service}>
            <StatusDot value={services[service]} />
            {service}
          </span>
        ))}
      </div>
    </div>
  );
}

function Shell({ activePage, setActivePage, health, children }) {
  return (
    <div className="app-shell">
      <HealthStrip health={health} />
      <aside className="side-panel">
        <div className="side-header">
          <span className="brand-mark large">AR</span>
          <div>
            <strong>Recruitment</strong>
            <span>Workflow Console</span>
          </div>
        </div>
        <nav className="side-nav">
          {navItems.map((item) => (
            <button
              className={activePage === item.id ? "nav-item active" : "nav-item"}
              key={item.id}
              onClick={() => setActivePage(item.id)}
              type="button"
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="main-panel">{children}</main>
    </div>
  );
}

function MetricCard({ label, value, detail, tone = "neutral" }) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      {detail ? <p>{detail}</p> : null}
    </article>
  );
}

function RunStatsTable({ runs }) {
  return (
    <div className="panel table-panel">
      <div className="panel-heading">
        <div>
          <h2>Runs</h2>
          <p>Recent workflow execution stats.</p>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Run</th>
              <th>Status</th>
              <th>Candidate</th>
              <th>Tokens</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {runs.length ? (
              runs.map((run) => (
                <tr key={run.run_id}>
                  <td className="mono">{run.run_id}</td>
                  <td>
                    <span className={`status-pill ${statusClass(run.status)}`}>{run.status}</span>
                  </td>
                  <td>{run.candidate_id || "Not applicable"}</td>
                  <td>{formatNumber(run.tokens)}</td>
                  <td>{formatDate(run.updated_at)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5">No runs have been recorded yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Dashboard({ dashboard, refreshDashboard }) {
  const runs = dashboard?.recent_runs || [];
  return (
    <div className="page-stack">
      <section className="page-title">
        <div>
          <span className="eyebrow">Home</span>
          <h1>Operations Dashboard</h1>
        </div>
        <button className="secondary-button" onClick={refreshDashboard} type="button">
          Refresh
        </button>
      </section>

      <section className="metric-grid">
        <MetricCard label="Active runs" value={formatNumber(dashboard?.runs_active)} detail="" />
        <MetricCard label="Success runs" value={formatNumber(dashboard?.runs_total)} detail="" />
        <MetricCard label="Failed runs" value={formatNumber(dashboard?.runs_failed)} detail="" tone="red" />
        <MetricCard label="Tokens consumed" value={formatNumber(dashboard?.tokens_consumed)} detail="" tone="blue" />
        <MetricCard label="Workflows setup" value={formatNumber(dashboard?.workflow_count)} detail="" />
        <MetricCard label="Agents setup" value={formatNumber(dashboard?.agent_count)} detail="" />
      </section>

      <section className="split-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Recruitment Stats</h2>
              <p>Workspace-backed candidate and job-opening counts.</p>
            </div>
          </div>
          <div className="stat-list">
            <div>
              <span>Candidates</span>
              <strong>{formatNumber(dashboard?.candidates_total)}</strong>
            </div>
            <div>
              <span>Job openings</span>
              <strong>{formatNumber(dashboard?.job_openings_total)}</strong>
            </div>
            <div>
              <span>Active openings</span>
              <strong>{formatNumber(dashboard?.active_job_openings)}</strong>
            </div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Workflow Inventory</h2>
              <p>Configured workflow entry points.</p>
            </div>
          </div>
          <div className="workflow-list">
            {(dashboard?.workflows || []).map((workflow) => (
              <div key={workflow.id}>
                <StatusDot value={workflow.status} />
                <span>{workflow.name}</span>
                <strong>{workflow.status}</strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <RunStatsTable runs={runs} />
    </div>
  );
}

function getWorkflowStepState(stepId, events, isComplete) {
  if (events.some((event) => event.type === "step_failed" && event.label === stepId)) {
    return "failed";
  }
  if (events.some((event) => event.type === "step_completed" && event.label === stepId)) {
    return "completed";
  }
  if (events.some((event) => event.type === "step_started" && event.label === stepId)) {
    return "current";
  }
  if (isComplete) {
    return "completed";
  }
  return "pending";
}

function getWorkflowStepUsage(stepId, events) {
  const completedEvents = events.filter(
    (event) =>
      event.stage === stepId &&
      event.type === "llm_call_completed" &&
      event.usage,
  );
  if (!completedEvents.length) {
    return null;
  }
  const modelNames = [...new Set(completedEvents.map((event) => event.model).filter(Boolean))];
  const usage = completedEvents.reduce(
    (totals, event) => {
      const eventUsage = event.usage || {};
      return {
        prompt_tokens: totals.prompt_tokens + Number(eventUsage.prompt_tokens || 0),
        completion_tokens: totals.completion_tokens + Number(eventUsage.completion_tokens || 0),
        total_tokens: totals.total_tokens + Number(eventUsage.total_tokens || 0),
      };
    },
    { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  );
  return {
    model: modelNames.join(", ") || "model unavailable",
    inputTokens: usage.prompt_tokens,
    outputTokens: usage.completion_tokens,
    totalTokens: usage.total_tokens || usage.prompt_tokens + usage.completion_tokens,
  };
}

function getWorkflowStepLatency(stepId, events) {
  const started = events.find((event) => event.type === "step_started" && event.label === stepId);
  const completed = [...events].reverse().find(
    (event) => event.type === "step_completed" && event.label === stepId,
  );
  const failed = [...events].reverse().find((event) => event.type === "step_failed" && event.label === stepId);
  if (!started?.timestamp) {
    return "";
  }
  const startTime = new Date(started.timestamp).getTime();
  const terminal = completed || failed;
  const endTime = terminal?.timestamp ? new Date(terminal.timestamp).getTime() : Date.now();
  return formatLatency(endTime - startTime);
}

function getWorkflowStepGuardrail(stepId, events) {
  const guardrailEvents = events.filter(
    (event) =>
      event.stage === stepId &&
      (event.type === "guardrail_started" || event.type === "guardrail_completed"),
  );
  if (!guardrailEvents.length) {
    return null;
  }
  const latest = guardrailEvents[guardrailEvents.length - 1];
  const latestCompleted = [...guardrailEvents]
    .reverse()
    .find((event) => event.type === "guardrail_completed");
  if (latest.type === "guardrail_started" && latestCompleted?.retry_count !== latest.retry_count) {
    return {
      state: "checking",
      label: latest.label || "Guardrail",
      message: "Guardrail checking",
    };
  }
  const completed = latest.type === "guardrail_completed" ? latest : latestCompleted;
  if (!completed) {
    return null;
  }
  return {
    state: completed.success ? "passed" : "failed",
    label: completed.label || "Guardrail",
    message: completed.success ? "Guardrail passed" : completed.error || completed.result || "Guardrail failed",
  };
}

function getWorkflowTotals(events, isComplete) {
  if (!isComplete || !events.length) {
    return null;
  }
  const started =
    events.find((event) => event.type === "run_started") ||
    events.find((event) => event.type === "run_queued") ||
    events[0];
  const terminal =
    [...events].reverse().find((event) => event.type === "run_completed" || event.type === "run_failed") ||
    events[events.length - 1];
  const startedAt = started?.timestamp ? new Date(started.timestamp).getTime() : NaN;
  const endedAt = terminal?.timestamp ? new Date(terminal.timestamp).getTime() : NaN;
  const totalTokens = events
    .filter((event) => event.type === "llm_call_completed" && event.usage)
    .reduce((sum, event) => {
      const usage = event.usage || {};
      return sum + Number(usage.total_tokens || Number(usage.prompt_tokens || 0) + Number(usage.completion_tokens || 0));
    }, 0);
  return {
    latency: Number.isFinite(startedAt) && Number.isFinite(endedAt) ? formatLatency(endedAt - startedAt) : "",
    totalTokens,
  };
}

function WorkflowStepper({ steps, events, isComplete, isTerminal = isComplete }) {
  const totals = getWorkflowTotals(events, isTerminal);
  return (
    <div className="stepper">
      {steps.map((step) => {
        const state = getWorkflowStepState(step.id, events, isComplete);
        const usage = getWorkflowStepUsage(step.id, events);
        const latency = getWorkflowStepLatency(step.id, events);
        const guardrail = getWorkflowStepGuardrail(step.id, events);
        const usageParts = usage
          ? [
              latency,
              usage.model,
              usage.inputTokens !== undefined ? `input ${formatNumber(usage.inputTokens)}` : "",
              usage.outputTokens !== undefined ? `output ${formatNumber(usage.outputTokens)}` : "",
            ].filter(Boolean)
          : [];
        return (
          <div className={`step-item ${state}`} key={step.id}>
            <span className="step-marker">
              {state === "completed" ? "✓" : state === "current" ? "" : "·"}
            </span>
            <span className="step-copy">
              <span>{step.label}</span>
              {usage ? (
                <span className="step-usage">{usageParts.join(" · ")}</span>
              ) : latency ? (
                <span className="step-usage">{latency}</span>
              ) : null}
              {guardrail ? (
                <span className={`guardrail-status ${guardrail.state}`}>
                  <span className="guardrail-icon">
                    {guardrail.state === "passed" ? "✓" : guardrail.state === "failed" ? "×" : "…"}
                  </span>
                  <span>{guardrail.message}</span>
                </span>
              ) : null}
            </span>
          </div>
        );
      })}
      {totals ? (
        <div className="workflow-total">
          <span>Total time {totals.latency || "not available"}</span>
          <span>Total tokens {formatNumber(totals.totalTokens)}</span>
        </div>
      ) : null}
    </div>
  );
}

function matchToneClass(value) {
  if (value === "good" || value === "match" || value === "excellent") {
    return "good";
  }
  if (value === "bad" || value === "mismatch" || value === "gap" || value === "major_gap" || value === "weak" || value === "not_recommended") {
    return "bad";
  }
  return "warning";
}

function MatchBadge({ match }) {
  if (!match) {
    return null;
  }
  return (
    <span className={`match-badge ${matchToneClass(match.severity || match.label)}`}>
      <strong>{match.percent ?? "N/A"}%</strong>
      <span>{match.label || "match"}</span>
    </span>
  );
}

function InsightList({ title, items, tone = "neutral" }) {
  const visibleItems = (items || []).filter(Boolean);
  if (!visibleItems.length) {
    return null;
  }
  return (
    <div className={`insight-list ${tone}`}>
      <h4>{title}</h4>
      <ul>
        {visibleItems.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function SkillTags({ title, items, tone }) {
  const visibleItems = (items || []).filter(Boolean);
  if (!visibleItems.length) {
    return null;
  }
  return (
    <div className="skill-tag-group">
      <h4>{title}</h4>
      <div className="tag-row">
        {visibleItems.map((item) => (
          <span className={`skill-tag ${tone}`} key={item}>
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function MatchResultPanel({ overview, runId }) {
  if (!overview) {
    return (
      <p className="muted result-placeholder">
        Select a candidate or upload a resume, then choose an opening to populate the analysis.
      </p>
    );
  }

  const sections = overview.sections || {};
  const overall = sections.overall_ai_analysis || {};
  const header = overview.header || {};
  const company = header.company_line || {};
  const skills = sections.skills || {};
  const criteriaRows = overview.criteria_grid?.rows || [];
  const otherFactors = sections.other_factors?.items || [];

  return (
    <div className="match-result">
      <section className="match-hero">
        <div>
          <span className="eyebrow">{company.company_name || "Job match"}</span>
          <h3>{overall.headline || header.jd_title}</h3>
          <p>{overall.overall_summary}</p>
          <div className="match-meta">
            {header.jd_title ? <span>{header.jd_title}</span> : null}
            {company.location ? <span>{company.location}</span> : null}
            {company.employment_type_display ? <span>{company.employment_type_display}</span> : null}
            {company.work_approach_display ? <span>{company.work_approach_display}</span> : null}
          </div>
          {header.pills?.length ? (
            <div className="tag-row">
              {header.pills.map((pill) => (
                <span className={`skill-tag ${matchToneClass(pill.severity)}`} key={pill.text}>
                  {pill.text}
                </span>
              ))}
            </div>
          ) : null}
        </div>
        <div className="overall-score-card">
          <span>Overall match</span>
          <strong>{header.overall_match?.percent ?? "N/A"}%</strong>
          <em>{overall.overall_fit_level || header.overall_match?.label || "N/A"}</em>
          <small>{runId ? `Run ${runId}` : ""}</small>
        </div>
      </section>

      <section className="match-scorecards">
        {(overview.scorecards || []).map((scorecard) => (
          <article key={scorecard.key || scorecard.title}>
            <span>{scorecard.title}</span>
            <MatchBadge match={scorecard.match} />
          </article>
        ))}
      </section>

      <section className="match-section-grid">
        <article>
          <div className="section-title-row">
            <h3>Experience</h3>
            <MatchBadge match={sections.experience?.match} />
          </div>
          <p>{sections.experience?.candidate_profile?.detail || sections.experience?.insight?.text}</p>
          <dl className="compact-dl">
            <div>
              <dt>Requirement</dt>
              <dd>{sections.experience?.job_requirement?.experience_level || "Not specified"}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{sections.experience?.insight?.confidence || "N/A"}</dd>
            </div>
          </dl>
        </article>
        <article>
          <div className="section-title-row">
            <h3>Designation</h3>
            <MatchBadge match={sections.designation_role?.match} />
          </div>
          <p>{sections.designation_role?.insight?.text}</p>
          <dl className="compact-dl">
            <div>
              <dt>Target titles</dt>
              <dd>{(sections.designation_role?.job_title_options || []).join(", ") || "Not specified"}</dd>
            </div>
            <div>
              <dt>Candidate titles</dt>
              <dd>{(sections.designation_role?.candidate_titles || []).join(", ") || "Not specified"}</dd>
            </div>
          </dl>
        </article>
      </section>

      <section className="match-section">
        <div className="section-title-row">
          <div>
            <h3>Skills Coverage</h3>
            <p>{skills.insight?.text}</p>
          </div>
          <MatchBadge match={skills.match} />
        </div>
        <div className="coverage-row">
          <span>Required skill overlap</span>
          <strong>{skills.coverage?.overlap_percent ?? "N/A"}%</strong>
          <em>{skills.coverage?.insight}</em>
        </div>
        <div className="skill-grid">
          <SkillTags title="Matched skills" items={skills.matched_skills} tone="good" />
          <SkillTags title="Missing or weak" items={skills.missing_or_weak_skills} tone="bad" />
          <SkillTags title="Bonus skills" items={skills.bonus_skills} tone="warning" />
        </div>
      </section>

      <section className="match-section-grid">
        <InsightList title="Key strengths" items={overall.key_strengths} tone="good" />
        <InsightList title="Key gaps" items={overall.key_gaps} tone="bad" />
        <InsightList title="Interview focus" items={overall.recommended_interview_focus} tone="warning" />
        <InsightList title="Better fit roles" items={overall.best_fit_roles} tone="neutral" />
      </section>

      <section className="match-section">
        <div className="section-title-row">
          <div>
            <h3>Recommendation</h3>
            <p>{overall.ideal_next_step}</p>
          </div>
          <span className={`recommendation-pill ${matchToneClass(overall.overall_fit_level)}`}>
            {overall.ai_recommendation || "Review"}
          </span>
        </div>
      </section>

      {otherFactors.length ? (
        <section className="match-section">
          <h3>Other Factors</h3>
          <div className="table-wrap compact-table">
            <table>
              <thead>
                <tr>
                  <th>Factor</th>
                  <th>JD Preference</th>
                  <th>Candidate</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {otherFactors.map((item) => (
                  <tr key={item.key}>
                    <td>{item.key}</td>
                    <td>{item.jd_preference}</td>
                    <td>{item.candidate_value}</td>
                    <td>
                      <span className={`status-pill ${statusClass(item.severity === "bad" ? "failed" : item.severity === "good" ? "completed" : "running")}`}>
                        {item.label}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {criteriaRows.length ? (
        <section className="match-section">
          <h3>Criteria Grid</h3>
          <div className="table-wrap compact-table">
            <table>
              <thead>
                <tr>
                  <th>Criterion</th>
                  <th>Requirement</th>
                  <th>Candidate evidence</th>
                  <th>Status</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {criteriaRows.map((row) => (
                  <tr key={row.criterion}>
                    <td>
                      <strong>{row.criterion}</strong>
                      <span className="table-subtext">{row.status_note}</span>
                    </td>
                    <td>{row.jd_requirement || "N/A"}</td>
                    <td>{row.cv_summary || "N/A"}</td>
                    <td>
                      <span className={`criteria-status ${matchToneClass(row.label)}`}>{row.label}</span>
                    </td>
                    <td>{row.score ?? "N/A"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function CandidatesTable({ candidates, onViewDetails }) {
  return (
    <div className="panel table-panel">
      <div className="panel-heading">
        <div>
          <h2>Candidate Records</h2>
          <p>Summaries aggregated from structured workspace artifacts.</p>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Role</th>
              <th>Location</th>
              <th>Skills</th>
              <th>Updated</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {candidates.length ? (
              candidates.map((candidate) => (
                <tr key={candidate.candidate_id}>
                  <td>
                    <strong>{candidate.full_name}</strong>
                    <span className="table-subtext">{candidate.candidate_id}</span>
                  </td>
                  <td>{candidate.primary_designation || "Not specified"}</td>
                  <td>{candidate.location || "Not specified"}</td>
                  <td>
                    {(candidate.skills || []).slice(0, 4).join(", ")}
                    {candidate.skill_count > 4 ? ` +${candidate.skill_count - 4}` : ""}
                  </td>
                  <td>{formatDate(candidate.updated_at)}</td>
                  <td>
                    <button className="secondary-button compact-button" type="button" onClick={() => onViewDetails(candidate)}>
                      Details
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="6">No candidate records have been curated yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CandidatesPage({ candidates, refreshCandidates, refreshDashboard }) {
  const [file, setFile] = useState(null);
  const [task, setTask] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedCandidateDetails, setSelectedCandidateDetails] = useState(null);
  const [isLoadingCandidateDetails, setIsLoadingCandidateDetails] = useState(false);

  useEffect(() => {
    if (!task?.task_id || ["SUCCESS", "FAILURE"].includes(task.state)) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      fetch(`${apiBase}/api/cv/tasks/${task.task_id}`)
        .then(parseJson)
        .then((payload) => {
          setTask(payload);
          if (payload.state === "SUCCESS") {
            refreshCandidates();
            refreshDashboard();
          } else if (payload.state === "FAILURE") {
            setError(payload.error || "Uploaded document does not appear to be a resume.");
          }
        })
        .catch((err) => setError(err.message));
    }, 1800);
    return () => window.clearInterval(timer);
  }, [task, refreshCandidates, refreshDashboard]);

  async function submit(event) {
    event.preventDefault();
    if (!file) {
      setError("Choose a resume before starting extraction.");
      return;
    }
    setError("");
    setTask(null);
    setEvents([]);
    setIsSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const payload = await fetch(`${apiBase}/api/cv/extract`, {
        method: "POST",
        body: formData,
      }).then(parseJson);
      setTask(payload);
      const source = new EventSource(`${apiBase}/api/cv/tasks/${payload.task_id}/events`);
      source.onmessage = (message) => {
        const eventPayload = JSON.parse(message.data);
        setEvents((current) => [...current, eventPayload]);
        if (eventPayload.type === "run_completed" || eventPayload.type === "run_failed") {
          if (eventPayload.type === "run_failed") {
            setTask((current) =>
              current ? { ...current, state: "FAILURE", error: eventPayload.error || current.error } : current,
            );
            setError(eventPayload.error || "Uploaded document does not appear to be a resume.");
          }
          source.close();
        }
      };
      source.onerror = () => {
        source.close();
      };
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function viewCandidateDetails(candidate) {
    setError("");
    setIsLoadingCandidateDetails(true);
    try {
      const jsonPath = candidate.structured_json_path || `candidates/${candidate.candidate_id}/resume_structured.json`;
      const markdownPath = candidate.structured_markdown_path || `candidates/${candidate.candidate_id}/resume.md`;
      const [jsonArtifact, markdownArtifact] = await Promise.all([
        fetch(`${apiBase}/api/workspace/${encodeURI(jsonPath)}`).then(parseJson),
        fetch(`${apiBase}/api/workspace/${encodeURI(markdownPath)}`).then(parseJson),
      ]);
      setSelectedCandidateDetails({
        candidate,
        structuredJson: jsonArtifact.content || "",
        markdown: markdownArtifact.content || "",
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingCandidateDetails(false);
    }
  }

  return (
    <section className="workflow-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">Workflow</span>
          <h1>Candidates</h1>
        </div>
      </div>
      <section className="split-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Resume Extraction</h2>
              <p>Upload a resume to create a structured candidate record.</p>
            </div>
          </div>
          <form className="form-stack form-offset" onSubmit={submit}>
            <label>
              <span>Resume file</span>
              <input
                className="field"
                type="file"
                accept=".pdf,.docx,.txt,.md"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </label>
            <button className="primary-button" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Starting..." : "Run Extraction"}
            </button>
          </form>
          {error ? <p className="error-box">{error}</p> : null}
        </div>
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Progress</h2>
              <p>{task ? `Task ${task.task_id}` : "No extraction task running."}</p>
            </div>
            {task ? <span className={`status-pill ${statusClass(task.state === "SUCCESS" ? "completed" : task.state === "FAILURE" ? "failed" : "running")}`}>{task.state}</span> : null}
          </div>
          <WorkflowStepper
            events={events}
            isComplete={task?.state === "SUCCESS"}
            isTerminal={task?.state === "SUCCESS" || task?.state === "FAILURE"}
            steps={extractionSteps}
          />
        </div>
      </section>

      {task?.state === "SUCCESS" ? (
        <section className="split-grid">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Structured JSON</h2>
                <p>Persisted candidate profile artifact.</p>
              </div>
            </div>
            <pre className="code-block">{task.artifacts?.structured_json || JSON.stringify(task.result?.structured_profile || {}, null, 2)}</pre>
          </div>
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Curated Markdown</h2>
                <p>Workspace-ready candidate record.</p>
              </div>
            </div>
            <pre className="code-block">{task.artifacts?.structured_markdown || "Markdown artifact not available."}</pre>
          </div>
        </section>
      ) : null}

      <CandidatesTable candidates={candidates} onViewDetails={viewCandidateDetails} />
      {isLoadingCandidateDetails ? <p className="muted">Loading candidate details...</p> : null}
      {selectedCandidateDetails ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setSelectedCandidateDetails(null)}>
          <div className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="candidate-details-title" onClick={(event) => event.stopPropagation()}>
            <div className="panel-heading">
              <div>
                <h2 id="candidate-details-title">{selectedCandidateDetails.candidate.full_name}</h2>
                <p>{selectedCandidateDetails.candidate.candidate_id}</p>
              </div>
              <button className="secondary-button compact-button" type="button" onClick={() => setSelectedCandidateDetails(null)}>
                Close
              </button>
            </div>
            <section className="split-grid">
              <div>
                <h3>Structured JSON</h3>
                <pre className="code-block">{selectedCandidateDetails.structuredJson}</pre>
              </div>
              <div>
                <h3>Curated Markdown</h3>
                <pre className="code-block">{selectedCandidateDetails.markdown}</pre>
              </div>
            </section>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function JobOpeningsPage({ jobs, refreshJobs, refreshDashboard }) {
  const [sourceType, setSourceType] = useState("pasted_text");
  const [content, setContent] = useState("");
  const [extractedJob, setExtractedJob] = useState(null);
  const [runInfo, setRunInfo] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedJobDetails, setSelectedJobDetails] = useState(null);
  const [updatingJobId, setUpdatingJobId] = useState("");
  const [statusNotice, setStatusNotice] = useState(null);

  useEffect(() => {
    if (!statusNotice) {
      return undefined;
    }
    const timer = window.setTimeout(() => setStatusNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [statusNotice]);

  async function submit(event) {
    event.preventDefault();
    if (!content.trim()) {
      setError(sourceType === "website" ? "Enter a job-posting URL." : "Paste a job description.");
      return;
    }
    setError("");
    setExtractedJob(null);
    setRunInfo(null);
    setEvents([]);
    setIsSubmitting(true);
    try {
      const payload = await fetch(`${apiBase}/api/recruitment/job-openings/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_type: sourceType,
          content,
        }),
      }).then(parseJson);
      setRunInfo(payload);
      let streamSettled = false;
      const loadTerminalRun = async (attempt = 0) => {
        const runPayload = await fetch(`${apiBase}/api/recruitment/job-openings/runs/${payload.run_id}`).then(parseJson);
        if (runPayload.status === "completed") {
          setExtractedJob(runPayload.result);
          setContent("");
          await Promise.all([refreshJobs(), refreshDashboard()]);
          setIsSubmitting(false);
          return true;
        }
        if (runPayload.status === "failed") {
          setError(runPayload.error || "Job opening curation failed.");
          setIsSubmitting(false);
          return true;
        }
        if (attempt < 5) {
          await new Promise((resolve) => window.setTimeout(resolve, 250));
          return loadTerminalRun(attempt + 1);
        }
        return false;
      };
      const source = new EventSource(`${apiBase}/api/recruitment/job-openings/runs/${payload.run_id}/events`);
      source.onmessage = async (message) => {
        const eventPayload = JSON.parse(message.data);
        setEvents((current) => [...current, eventPayload]);
        if (eventPayload.type === "run_completed" || eventPayload.type === "run_failed") {
          streamSettled = true;
          source.close();
          try {
            const resolved = await loadTerminalRun();
            if (!resolved) {
              setError("Job opening curation finished, but the final result was not available yet.");
              setIsSubmitting(false);
            }
          } catch (err) {
            setError(err.message);
            setIsSubmitting(false);
          }
        }
      };
      source.onerror = async () => {
        if (streamSettled) {
          return;
        }
        streamSettled = true;
        source.close();
        try {
          const resolved = await loadTerminalRun();
          if (!resolved) {
            setError("The curation progress stream disconnected before completion.");
            setIsSubmitting(false);
          }
        } catch (err) {
          setError(err.message);
          setIsSubmitting(false);
        }
      };
    } catch (err) {
      setError(err.message);
      setIsSubmitting(false);
    }
  }

  async function updateJobStatus(job, status) {
    setError("");
    setUpdatingJobId(job.id);
    try {
      const updated = await fetch(`${apiBase}/api/recruitment/job-openings/${job.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      }).then(parseJson);
      if (selectedJobDetails?.id === job.id) {
        setSelectedJobDetails(updated);
      }
      await Promise.all([refreshJobs(), refreshDashboard()]);
      setStatusNotice({
        id: `${job.id}-${Date.now()}`,
        message: `${job.title} is now ${status}.`,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingJobId("");
    }
  }

  return (
    <section className="workflow-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">Workflow</span>
          <h1>Job Opening Curation</h1>
        </div>
      </div>
      <div className="split-grid">
        <div className="panel">
          <form className="form-stack" onSubmit={submit}>
            <div className="segmented-control">
              <button
                className={sourceType === "pasted_text" ? "active" : ""}
                onClick={() => setSourceType("pasted_text")}
                type="button"
              >
                Pasted Text
              </button>
              <button
                className={sourceType === "website" ? "active" : ""}
                onClick={() => setSourceType("website")}
                type="button"
              >
                Website
              </button>
            </div>
            {sourceType === "website" ? (
              <label>
                <span>Job posting URL</span>
                <input
                  className="field"
                  placeholder="https://example.com/jobs/ui-ux-designer"
                  type="url"
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                />
              </label>
            ) : (
              <label>
                <span>Job description text</span>
                <textarea
                  className="field min-h tall-textarea"
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                />
              </label>
            )}
            <button className="primary-button" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Curating..." : "Curate And Store Opening"}
            </button>
          </form>
          {error ? <p className="error-box">{error}</p> : null}
          {extractedJob ? (
            <p className="success-box">
              Stored JSON at {extractedJob.json_path} and Markdown at {extractedJob.markdown_path}.
            </p>
          ) : null}
        </div>
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Progress</h2>
              <p>{runInfo ? `Run ${runInfo.run_id}` : "No curation run active."}</p>
            </div>
            {runInfo ? (
              <span className={`status-pill ${statusClass(extractedJob ? "completed" : error ? "failed" : "running")}`}>
                {extractedJob ? "completed" : error ? "failed" : "running"}
              </span>
            ) : null}
          </div>
          <WorkflowStepper
            events={events}
            isComplete={Boolean(extractedJob)}
            steps={sourceType === "website" ? jobOpeningWebsiteSteps : jobOpeningTextSteps}
          />
        </div>
      </div>
      {extractedJob ? (
        <section className="split-grid">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Structured Job JSON</h2>
                <p>Annotated model stored in the workspace.</p>
              </div>
            </div>
            <div className="quality-summary">
              <div className="quality-score compact">
                <span>Confidence</span>
                <strong>{Math.round((extractedJob.job_opening.metadata?.confidence || 0) * 100)}%</strong>
              </div>
              <div>
                <span className="eyebrow">Missing fields</span>
                <div className="tag-row">
                  {(extractedJob.job_opening.metadata?.missing_fields || []).length ? (
                    extractedJob.job_opening.metadata.missing_fields.map((field) => (
                      <span className="warning-tag" key={field}>{field}</span>
                    ))
                  ) : (
                    <span className="ok-tag">None</span>
                  )}
                </div>
              </div>
            </div>
            <pre className="code-block">{JSON.stringify(extractedJob.job_opening, null, 2)}</pre>
          </div>
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>Curated Markdown</h2>
                <p>Clean recruiter-facing job opening record.</p>
              </div>
            </div>
            <pre className="code-block">{extractedJob.markdown}</pre>
          </div>
        </section>
      ) : null}
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Stored Openings</h2>
            <p>Workspace artifacts available for matching.</p>
          </div>
        </div>
        <div className="job-list">
          {jobs.length ? (
            jobs.map((job) => (
              <article key={job.id}>
                <div className="job-card-header">
                  <div>
                    <h3>{job.title}</h3>
                    <p>{[job.company_name, job.location].filter(Boolean).join(" · ") || "Details pending"}</p>
                  </div>
                  <span className={`status-pill ${statusClass(formatJobStatus(job.status))}`}>
                    {formatJobStatus(job.status)}
                  </span>
                </div>
                <div className="job-card-actions">
                  <label className="circle-checkbox-control">
                    <input
                      checked={formatJobStatus(job.status) === "active"}
                      disabled={updatingJobId === job.id}
                      type="checkbox"
                      onChange={(event) => updateJobStatus(job, event.target.checked ? "active" : "inactive")}
                    />
                    <span className="circle-checkbox" aria-hidden="true" />
                    <span>{updatingJobId === job.id ? "Updating" : "Active"}</span>
                  </label>
                  <button className="secondary-button compact-button" type="button" onClick={() => setSelectedJobDetails(job)}>
                    View Details
                  </button>
                </div>
                <span>{job.json_path}</span>
              </article>
            ))
          ) : (
            <p className="muted">No job openings stored yet.</p>
          )}
        </div>
      </div>
      {selectedJobDetails ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setSelectedJobDetails(null)}>
          <div className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="job-details-title" onClick={(event) => event.stopPropagation()}>
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Job Opening</span>
                <h2 id="job-details-title">{selectedJobDetails.title}</h2>
                <p>{[selectedJobDetails.company_name, selectedJobDetails.location].filter(Boolean).join(" · ") || "Details pending"}</p>
              </div>
              <button className="secondary-button compact-button" type="button" onClick={() => setSelectedJobDetails(null)}>
                Close
              </button>
            </div>
            <div className="modal-summary">
              <div>
                <span>Status</span>
                <strong>{formatJobStatus(selectedJobDetails.status)}</strong>
              </div>
              <div>
                <span>Created</span>
                <strong>{formatDate(selectedJobDetails.created_at)}</strong>
              </div>
              <div>
                <span>Updated</span>
                <strong>{formatDate(selectedJobDetails.updated_at)}</strong>
              </div>
            </div>
            <pre className="code-block">{JSON.stringify(selectedJobDetails, null, 2)}</pre>
          </div>
        </div>
      ) : null}
      {statusNotice ? (
        <div className="side-toast-pill" key={statusNotice.id} role="status">
          {statusNotice.message}
        </div>
      ) : null}
    </section>
  );
}

function MatchingPage({ candidates, jobs, refreshDashboard }) {
  const [candidateSource, setCandidateSource] = useState("existing");
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [file, setFile] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [runInfo, setRunInfo] = useState(null);
  const [events, setEvents] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) || jobs[0] || null,
    [jobs, selectedJobId],
  );
  const selectedCandidate = useMemo(
    () => candidates.find((candidate) => candidate.candidate_id === selectedCandidateId) || candidates[0] || null,
    [candidates, selectedCandidateId],
  );

  useEffect(() => {
    if (!selectedJobId && jobs[0]?.id) {
      setSelectedJobId(jobs[0].id);
    }
  }, [jobs, selectedJobId]);

  useEffect(() => {
    if (!selectedCandidateId && candidates[0]?.candidate_id) {
      setSelectedCandidateId(candidates[0].candidate_id);
    }
  }, [candidates, selectedCandidateId]);

  async function watchRun(data) {
    setRunInfo(data);
    let streamSettled = false;
    const loadTerminalRun = async (attempt = 0) => {
      const runPayload = await fetch(`${apiBase}/api/orchestration/runs/${data.run_id}`).then(parseJson);
      if (runPayload.status === "completed") {
        setAnalysis(runPayload.result);
        setIsSubmitting(false);
        refreshDashboard();
        return true;
      }
      if (runPayload.status === "failed") {
        setError(runPayload.error || "The match analysis run failed.");
        setIsSubmitting(false);
        return true;
      }
      if (attempt < 5) {
        await new Promise((resolve) => window.setTimeout(resolve, 250));
        return loadTerminalRun(attempt + 1);
      }
      return false;
    };
    const source = new EventSource(`${apiBase}/api/orchestration/runs/${data.run_id}/events`);
    source.onmessage = async (message) => {
      const payload = JSON.parse(message.data);
      setEvents((current) => [...current, payload]);
      if (payload.type === "run_completed" || payload.type === "run_failed") {
        streamSettled = true;
        source.close();
        try {
          const resolved = await loadTerminalRun();
          if (!resolved) {
            setError("Match analysis finished, but the final result was not available yet.");
            setIsSubmitting(false);
          }
        } catch (err) {
          setError(err.message);
          setIsSubmitting(false);
        }
      }
    };
    source.onerror = async () => {
      if (streamSettled) {
        return;
      }
      streamSettled = true;
      source.close();
      try {
        const resolved = await loadTerminalRun();
        if (!resolved) {
          setError("The match analysis progress stream disconnected before completion.");
          setIsSubmitting(false);
        }
      } catch (err) {
        setError(err.message);
        setIsSubmitting(false);
      }
    };
  }

  async function submit(event) {
    event.preventDefault();
    if (!selectedJob) {
      setError("Choose a stored job opening before running match analysis.");
      return;
    }
    if (candidateSource === "existing" && !selectedCandidate) {
      setError("Choose a candidate or switch to resume upload.");
      return;
    }
    if (candidateSource === "upload" && !file) {
      setError("Upload a resume or switch to candidate selection.");
      return;
    }
    setError("");
    setRunInfo(null);
    setEvents([]);
    setAnalysis(null);
    setIsSubmitting(true);
    try {
      const jobPayload = {
        job_title: selectedJob.title,
        company_name: selectedJob.company_name || "",
        location: selectedJob.location || "",
        skills_csv: selectedJob.skills_csv || (selectedJob.skills_required || []).join(", "),
        job_description: selectedJob.description || "",
      };
      if (candidateSource === "existing") {
        const data = await fetch(`${apiBase}/api/orchestration/stored-candidate-runs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            candidate_id: selectedCandidate.candidate_id,
            ...jobPayload,
          }),
        }).then(parseJson);
        watchRun(data);
        return;
      }
      const formData = new FormData();
      formData.append("file", file);
      Object.entries(jobPayload).forEach(([key, value]) => formData.append(key, value));
      const data = await fetch(`${apiBase}/api/orchestration/runs`, {
        method: "POST",
        body: formData,
      }).then(parseJson);
      watchRun(data);
    } catch (err) {
      setError(err.message);
      setIsSubmitting(false);
    }
  }

  const overview = analysis?.matching?.jd_match_overview;

  return (
    <section className="workflow-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">Workflow</span>
          <h1>Match Analysis</h1>
        </div>
      </div>
      <div className="split-grid">
        <div className="panel">
          <form className="form-stack" onSubmit={submit}>
            <div className="segmented-control">
              <button
                className={candidateSource === "existing" ? "active" : ""}
                onClick={() => {
                  setCandidateSource("existing");
                  setFile(null);
                }}
                type="button"
              >
                Existing Candidate
              </button>
              <button
                className={candidateSource === "upload" ? "active" : ""}
                onClick={() => {
                  setCandidateSource("upload");
                  setSelectedCandidateId("");
                }}
                type="button"
              >
                Upload Resume
              </button>
            </div>
            {candidateSource === "existing" ? (
              <label>
                <span>Candidate</span>
                <select
                  className="field"
                  value={selectedCandidate?.candidate_id || ""}
                  onChange={(event) => setSelectedCandidateId(event.target.value)}
                >
                  {candidates.map((candidate) => (
                    <option key={candidate.candidate_id} value={candidate.candidate_id}>
                      {candidate.full_name} {candidate.primary_designation ? `- ${candidate.primary_designation}` : ""}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <label>
                <span>Resume file</span>
                <input className="field" type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setFile(event.target.files?.[0] || null)} />
              </label>
            )}
            <label>
              <span>Job opening</span>
              <select className="field" value={selectedJob?.id || ""} onChange={(event) => setSelectedJobId(event.target.value)}>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title} {job.company_name ? `- ${job.company_name}` : ""}
                  </option>
                ))}
              </select>
            </label>
            {selectedJob ? (
              <div className="selected-job">
                <strong>{selectedJob.title}</strong>
                <p>{selectedJob.description || "No description provided."}</p>
              </div>
            ) : null}
            <button className="primary-button" disabled={isSubmitting || !jobs.length} type="submit">
              {isSubmitting ? "Running..." : "Run Match Analysis"}
            </button>
          </form>
          {error ? <p className="error-box">{error}</p> : null}
        </div>
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Progress</h2>
              <p>{runInfo ? `Run ${runInfo.run_id}` : "No match analysis running."}</p>
            </div>
            {runInfo ? (
              <span className={`status-pill ${statusClass(analysis ? "completed" : error ? "failed" : "running")}`}>
                {analysis ? "completed" : error ? "failed" : "running"}
              </span>
            ) : null}
          </div>
          <WorkflowStepper
            events={events}
            isComplete={Boolean(analysis)}
            steps={candidateSource === "existing" ? storedCandidateMatchingSteps : matchingSteps}
          />
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Match Result</h2>
            <p>{overview ? "Recruiter-facing fit analysis and evidence." : "Waiting for a run."}</p>
          </div>
          {overview?.header?.overall_match ? <MatchBadge match={overview.header.overall_match} /> : null}
        </div>
        <MatchResultPanel overview={overview} runId={runInfo?.run_id} />
      </div>
    </section>
  );
}

function SettingsPage() {
  const [form, setForm] = useState({
    max_cost_usd: "",
    max_latency_seconds: "",
  });
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetch(`${apiBase}/api/settings/containment`)
      .then(parseJson)
      .then((payload) => {
        setForm({
          max_cost_usd: payload.max_cost_usd ?? "",
          max_latency_seconds: payload.max_latency_seconds ?? "",
        });
      })
      .catch((err) => setError(err.message));
  }, []);

  function updateField(field, value) {
    setSaved(false);
    setForm((current) => ({ ...current, [field]: value }));
  }

  function numericOrNull(value) {
    return value === "" ? null : Number(value);
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSaved(false);
    setIsSaving(true);
    try {
      const payload = await fetch(`${apiBase}/api/settings/containment`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_cost_usd: numericOrNull(form.max_cost_usd),
          max_latency_seconds: numericOrNull(form.max_latency_seconds),
        }),
      }).then(parseJson);
      setForm({
        max_cost_usd: payload.max_cost_usd ?? "",
        max_latency_seconds: payload.max_latency_seconds ?? "",
      });
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="workflow-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">Administration</span>
          <h1>Settings</h1>
        </div>
      </div>
      <div className="panel narrow-panel">
        <div className="panel-heading">
          <div>
            <h2>Containment Limits</h2>
            <p>Applied when new CrewAI workflow runs start.</p>
          </div>
        </div>
        <form className="form-stack form-offset" onSubmit={submit}>
          <label>
            <span>Max token cost USD</span>
            <input
              className="field"
              min="0"
              step="0.001"
              type="number"
              value={form.max_cost_usd}
              onChange={(event) => updateField("max_cost_usd", event.target.value)}
            />
          </label>
          <label>
            <span>Max latency seconds</span>
            <input
              className="field"
              min="0"
              step="1"
              type="number"
              value={form.max_latency_seconds}
              onChange={(event) => updateField("max_latency_seconds", event.target.value)}
            />
          </label>
          <button className="primary-button" disabled={isSaving} type="submit">
            {isSaving ? "Saving..." : "Save Settings"}
          </button>
        </form>
        {error ? <p className="error-box">{error}</p> : null}
        {saved ? <p className="success-box">Containment settings updated.</p> : null}
      </div>
    </section>
  );
}

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [health, setHealth] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");

  async function refreshHealth() {
    try {
      setHealth(await fetch(`${apiBase}/health`).then(parseJson));
    } catch (err) {
      setHealth({ status: "degraded", services: {}, error: err.message });
    }
  }

  async function refreshDashboard() {
    try {
      setDashboard(await fetch(`${apiBase}/api/recruitment/dashboard`).then(parseJson));
    } catch (err) {
      setError(err.message);
    }
  }

  async function refreshJobs() {
    try {
      const payload = await fetch(`${apiBase}/api/recruitment/job-openings`).then(parseJson);
      setJobs(payload.job_openings || []);
    } catch (err) {
      setError(err.message);
    }
  }

  async function refreshCandidates() {
    try {
      const payload = await fetch(`${apiBase}/api/recruitment/candidates`).then(parseJson);
      setCandidates(payload.candidates || []);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refreshHealth();
    refreshDashboard();
    refreshCandidates();
    refreshJobs();
    const timer = window.setInterval(refreshHealth, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const page = {
    dashboard: <Dashboard dashboard={dashboard} refreshDashboard={refreshDashboard} />,
    candidates: (
      <CandidatesPage
        candidates={candidates}
        refreshCandidates={refreshCandidates}
        refreshDashboard={refreshDashboard}
      />
    ),
    jobs: <JobOpeningsPage jobs={jobs} refreshJobs={refreshJobs} refreshDashboard={refreshDashboard} />,
    matching: <MatchingPage candidates={candidates} jobs={jobs} refreshDashboard={refreshDashboard} />,
    settings: <SettingsPage />,
  }[activePage];

  return (
    <Shell activePage={activePage} health={health} setActivePage={setActivePage}>
      {error ? <p className="error-box global-error">{error}</p> : null}
      {page}
    </Shell>
  );
}
