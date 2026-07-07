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
  { id: "curate_structured_markdown", label: "Curate Markdown" },
  { id: "persist_outputs", label: "Persist artifacts" },
];

const matchingSteps = [
  { id: "parse_document", label: "Parse document" },
  { id: "validate_document", label: "Validate resume" },
  { id: "extract_structured_profile", label: "Extract structured JSON" },
  { id: "curate_structured_markdown", label: "Curate Markdown" },
  { id: "persist_outputs", label: "Persist candidate artifacts" },
  { id: "build_matching_context", label: "Build matching context" },
  { id: "run_match_analysis", label: "Run match analysis" },
  { id: "assemble_match_results", label: "Assemble results" },
];

const storedCandidateMatchingSteps = [
  { id: "build_matching_context", label: "Build matching context" },
  { id: "run_match_analysis", label: "Run match analysis" },
  { id: "assemble_match_results", label: "Assemble results" },
];

const jobOpeningTextSteps = [
  { id: "read_pasted_text", label: "Read pasted text" },
  { id: "extract_structured_job", label: "Extract structured job" },
  { id: "quality_guardrail", label: "Quality guardrail" },
  { id: "persist_job_opening", label: "Persist artifacts" },
];

const jobOpeningWebsiteSteps = [
  { id: "fetch_source_content", label: "Fetch and clean website" },
  { id: "extract_structured_job", label: "Extract structured job" },
  { id: "quality_guardrail", label: "Quality guardrail" },
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
        <MetricCard label="Active runs" value={formatNumber(dashboard?.runs_active)} detail="" />|
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
  const llmEvents = events.filter(
    (event) =>
      event.stage === stepId &&
      (event.type === "llm_call_started" || event.type === "llm_call_completed"),
  );
  if (!llmEvents.length) {
    return null;
  }
  const latest = llmEvents[llmEvents.length - 1];
  const completed = [...llmEvents].reverse().find((event) => event.type === "llm_call_completed");
  const usage = completed?.usage || latest?.usage || {};
  return {
    model: latest.model || completed?.model || "model pending",
    inputTokens: usage.prompt_tokens,
    outputTokens: completed?.usage?.completion_tokens,
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

function WorkflowStepper({ steps, events, isComplete }) {
  return (
    <div className="stepper">
      {steps.map((step) => {
        const state = getWorkflowStepState(step.id, events, isComplete);
        const usage = getWorkflowStepUsage(step.id, events);
        const latency = getWorkflowStepLatency(step.id, events);
        return (
          <div className={`step-item ${state}`} key={step.id}>
            <span className="step-marker">
              {state === "completed" ? "✓" : state === "current" ? "" : "·"}
            </span>
            <span className="step-copy">
              <span>{step.label}</span>
              {usage ? (
                <span className="step-usage">
                  {usage.model}
                  {latency ? ` · ${latency}` : ""}
                  {usage.inputTokens !== undefined ? ` · input ${formatNumber(usage.inputTokens)}` : ""}
                  {usage.outputTokens !== undefined ? ` · output ${formatNumber(usage.outputTokens)}` : ""}
                </span>
              ) : latency ? (
                <span className="step-usage">{latency}</span>
              ) : null}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function CandidatesTable({ candidates }) {
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
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5">No candidate records have been curated yet.</td>
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

      <CandidatesTable candidates={candidates} />
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
      const source = new EventSource(`${apiBase}/api/recruitment/job-openings/runs/${payload.run_id}/events`);
      source.onmessage = async (message) => {
        const eventPayload = JSON.parse(message.data);
        setEvents((current) => [...current, eventPayload]);
        if (eventPayload.type === "run_completed" || eventPayload.type === "run_failed") {
          source.close();
          const runPayload = await fetch(`${apiBase}/api/recruitment/job-openings/runs/${payload.run_id}`).then(parseJson);
          if (runPayload.status === "completed") {
            setExtractedJob(runPayload.result);
            setContent("");
            await Promise.all([refreshJobs(), refreshDashboard()]);
          } else {
            setError(runPayload.error || "Job opening curation failed.");
          }
          setIsSubmitting(false);
        }
      };
      source.onerror = () => {
        source.close();
        setError("The curation progress stream disconnected before completion.");
        setIsSubmitting(false);
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
    const source = new EventSource(`${apiBase}/api/orchestration/runs/${data.run_id}/events`);
    source.onmessage = async (message) => {
      const payload = JSON.parse(message.data);
      setEvents((current) => [...current, payload]);
      if (payload.type === "run_completed" || payload.type === "run_failed") {
        source.close();
        const runPayload = await fetch(`${apiBase}/api/orchestration/runs/${data.run_id}`).then(parseJson);
        if (runPayload.status === "completed") {
          setAnalysis(runPayload.result);
        } else {
          setError(runPayload.error || "The match analysis run failed.");
        }
        setIsSubmitting(false);
        refreshDashboard();
      }
    };
    source.onerror = () => {
      source.close();
      setError("The live progress stream disconnected before the run completed.");
      setIsSubmitting(false);
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
            <p>{runInfo ? `Run ${runInfo.run_id}` : "Waiting for a run."}</p>
          </div>
          {overview?.header?.overall_match ? (
            <span className="score-badge">{overview.header.overall_match.percent}%</span>
          ) : null}
        </div>
        {overview ? (
          <div className="result-summary">
            <h3>{overview.sections?.overall_ai_analysis?.headline || overview.header?.jd_title}</h3>
            <p>{overview.sections?.overall_ai_analysis?.overall_summary}</p>
            <div className="stat-list compact">
              <div>
                <span>Fit</span>
                <strong>{overview.sections?.overall_ai_analysis?.overall_fit_level || "N/A"}</strong>
              </div>
              <div>
                <span>Next step</span>
                <strong>{overview.sections?.overall_ai_analysis?.ideal_next_step || "N/A"}</strong>
              </div>
            </div>
          </div>
          ) : (
          <p className="muted result-placeholder">Select a candidate or upload a resume, then choose an opening to populate the analysis.</p>
        )}
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
