import React, { useEffect, useState } from "react";

const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function parseJson(response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return response.json();
}

async function loadSampleResume(sampleId) {
  const response = await fetch(`${apiBase}/api/samples/${sampleId}/resume`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to load sample resume.");
  }
  const blob = await response.blob();
  const contentDisposition = response.headers.get("content-disposition") || "";
  const match = contentDisposition.match(/filename="?([^"]+)"?/i);
  const filename = match?.[1] || `${sampleId}.txt`;
  return new File([blob], filename, { type: blob.type || "text/plain" });
}

function formatEventType(type) {
  return type.replaceAll("_", " ");
}

function formatStage(stage) {
  return (stage || "candidate_analysis").replaceAll("_", " ");
}

function formatCurrency(value) {
  if (typeof value !== "number") {
    return null;
  }
  return `$${value.toFixed(value < 0.01 ? 6 : 4)}`;
}

function getStageGroups(events) {
  const groups = [];
  const byStage = new Map();

  for (const event of events) {
    const stageKey = event.stage || "candidate_analysis";
    if (!byStage.has(stageKey)) {
      const group = { stage: stageKey, events: [] };
      byStage.set(stageKey, group);
      groups.push(group);
    }
    byStage.get(stageKey).events.push(event);
  }

  return groups.map((group) => {
    const latestEvent = group.events[group.events.length - 1];
    const hasFailure = group.events.some((event) => event.type.includes("failed"));
    const hasGuardrailFailure = group.events.some(
      (event) => event.type === "guardrail_completed" && event.success === false,
    );
    const llmCalls = group.events.filter((event) => event.type === "llm_call_completed");
    const totalCost = llmCalls.reduce(
      (sum, event) => sum + (typeof event.estimated_cost_usd === "number" ? event.estimated_cost_usd : 0),
      0,
    );
    const totalTokens = llmCalls.reduce(
      (sum, event) => sum + (event.usage?.total_tokens || 0),
      0,
    );

    return {
      ...group,
      latestEvent,
      hasFailure,
      hasGuardrailFailure,
      llmCallCount: llmCalls.length,
      totalCost,
      totalTokens,
    };
  });
}

function StepPill({ event }) {
  const isFailure = event.type.includes("failed");
  const isGuardrailWarning = event.type === "guardrail_completed" && event.success === false;
  const hasDetails =
    event.message ||
    event.error ||
    event.task_name ||
    event.guardrail_type ||
    event.retry_count !== undefined ||
    event.model ||
    event.usage ||
    event.estimated_cost_usd !== undefined ||
    event.finish_reason ||
    event.agent_role;

  const pillClass = isFailure
    ? "bg-red-100 text-red-700"
    : isGuardrailWarning
      ? "bg-ember-100 text-ember-700"
      : "bg-moss-100 text-moss-700";

  if (!hasDetails) {
    return (
      <span className={`inline-flex rounded-full px-3 py-1 text-[0.68rem] uppercase tracking-[0.14em] ${pillClass}`}>
        {formatEventType(event.type)}
      </span>
    );
  }

  const usage = event.usage || {};

  return (
    <details className="group inline-block">
      <summary
        className={`list-none cursor-pointer rounded-full px-3 py-1 text-[0.68rem] uppercase tracking-[0.14em] ${pillClass}`}
      >
        {formatEventType(event.type)}
      </summary>
      <div className="mt-3 w-[min(26rem,80vw)] rounded-2xl border border-moss-900/10 bg-white p-4 text-sm text-moss-700 shadow-sm">
        {event.message ? <p>{event.message}</p> : null}
        <div className="mt-3 grid gap-2">
          {event.agent_role ? <p><span className="font-medium text-moss-900">Agent:</span> {event.agent_role}</p> : null}
          {event.task_name ? <p><span className="font-medium text-moss-900">Task:</span> {event.task_name}</p> : null}
          {event.guardrail_type ? <p><span className="font-medium text-moss-900">Guardrail:</span> {event.guardrail_type}</p> : null}
          {event.retry_count !== undefined ? <p><span className="font-medium text-moss-900">Retry:</span> {event.retry_count}</p> : null}
          {event.model ? <p><span className="font-medium text-moss-900">Model:</span> {event.model}</p> : null}
          {event.finish_reason ? <p><span className="font-medium text-moss-900">Finish:</span> {event.finish_reason}</p> : null}
          {event.call_id ? <p><span className="font-medium text-moss-900">Call ID:</span> {event.call_id}</p> : null}
          {usage.total_tokens ? (
            <p>
              <span className="font-medium text-moss-900">Tokens:</span>{" "}
              total {usage.total_tokens}, prompt {usage.prompt_tokens || 0}, completion {usage.completion_tokens || 0}
              {usage.cached_prompt_tokens ? `, cached ${usage.cached_prompt_tokens}` : ""}
            </p>
          ) : null}
          {event.estimated_cost_usd !== undefined && event.estimated_cost_usd !== null ? (
            <p><span className="font-medium text-moss-900">Estimated cost:</span> {formatCurrency(event.estimated_cost_usd)}</p>
          ) : null}
          {event.error ? <p className="text-red-700"><span className="font-medium">Error:</span> {event.error}</p> : null}
          <p><span className="font-medium text-moss-900">At:</span> {event.timestamp}</p>
        </div>
      </div>
    </details>
  );
}

export default function App() {
  const [health, setHealth] = useState("loading");
  const [samples, setSamples] = useState([]);
  const [selectedSampleId, setSelectedSampleId] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [location, setLocation] = useState("");
  const [skillsCsv, setSkillsCsv] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileSourceLabel, setFileSourceLabel] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [runInfo, setRunInfo] = useState(null);
  const [progressEvents, setProgressEvents] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${apiBase}/health`)
      .then(parseJson)
      .then((data) => setHealth(data.status))
      .catch((err) => setHealth(`error: ${err.message}`));

    fetch(`${apiBase}/api/samples`)
      .then(parseJson)
      .then((data) => {
        const sampleItems = data.samples || [];
        setSamples(sampleItems);
        if (sampleItems.length > 0) {
          applySample(sampleItems[0]);
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  function applySample(sample) {
    setSelectedSampleId(sample.id);
    setJobTitle(sample.job.job_title);
    setCompanyName(sample.job.company_name);
    setLocation(sample.job.location);
    setSkillsCsv(sample.job.skills_csv);
    setJobDescription(sample.job.job_description);
  }

  async function handleLoadSampleResume() {
    if (!selectedSampleId) {
      return;
    }
    setError("");
    setIsLoadingSample(true);
    try {
      const file = await loadSampleResume(selectedSampleId);
      setSelectedFile(file);
      setFileSourceLabel(file.name);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingSample(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setAnalysis(null);
    setRunInfo(null);
    setProgressEvents([]);
    if (!selectedFile) {
      setError("Choose your own CV or load a sample resume before running the orchestration.");
      return;
    }

    setIsSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("job_title", jobTitle);
      formData.append("company_name", companyName);
      formData.append("location", location);
      formData.append("skills_csv", skillsCsv);
      formData.append("job_description", jobDescription);

      const data = await fetch(`${apiBase}/api/orchestration/runs`, {
        method: "POST",
        body: formData,
      }).then(parseJson);
      setRunInfo(data);

      const eventSource = new EventSource(`${apiBase}/api/orchestration/runs/${data.run_id}/events`);
      eventSource.onmessage = async (message) => {
        const payload = JSON.parse(message.data);
        setProgressEvents((current) => [...current, payload]);

        if (payload.type === "run_completed" || payload.type === "run_failed") {
          eventSource.close();
          const runPayload = await fetch(`${apiBase}/api/orchestration/runs/${data.run_id}`).then(parseJson);
          if (runPayload.status === "completed") {
            setAnalysis(runPayload.result);
          } else {
            setError(runPayload.error || "The orchestration run failed.");
          }
          setIsSubmitting(false);
        }
      };
      eventSource.onerror = () => {
        eventSource.close();
        setError("The live progress stream disconnected before the run completed.");
        setIsSubmitting(false);
      };
    } catch (err) {
      setError(err.message);
      setIsSubmitting(false);
    }
  }

  const selectedSample = samples.find((sample) => sample.id === selectedSampleId) || null;
  const trace = analysis?.trace || [];
  const matchSummary = analysis?.matching?.jd_match_overview?.sections?.overall_ai_analysis || null;
  const extractionNotes = analysis?.extraction?.structured_profile?.extraction_notes || [];
  const stageGroups = getStageGroups(progressEvents);
  const currentStage = stageGroups.length ? stageGroups[stageGroups.length - 1] : null;

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <section className="mb-6 grid gap-5 lg:grid-cols-[1.8fr_0.8fr]">
        <div>
          <p className="mb-2 text-xs uppercase tracking-[0.22em] text-moss-600">
            Multi-Agent Orchestration
          </p>
          <h1 className="max-w-4xl font-display text-4xl leading-none text-moss-900 sm:text-6xl">
            Start from real sample inputs, run the pipeline once, and inspect every handoff.
          </h1>
          <p className="mt-4 max-w-3xl text-sm text-moss-700 sm:text-base">
            This UI drives a reviewer-facing orchestration endpoint that extracts a candidate
            profile, validates the handoff contract, compares it to a vacancy, and exposes the
            full structured result plus execution trace.
          </p>
        </div>

        <aside className="glass-card grid content-center gap-4 p-5">
          <div>
            <span className="meta-label">Backend health</span>
            <strong className="text-lg text-moss-900">{health}</strong>
          </div>
          <div>
            <span className="meta-label">Model mode</span>
            <strong className="text-lg text-moss-900">
              {analysis ? `${analysis.model_provider} / ${analysis.model_mode}` : "pending"}
            </strong>
          </div>
          <div>
            <span className="meta-label">Current stage</span>
            <strong className="text-lg text-moss-900">
              {currentStage ? formatStage(currentStage.stage) : "idle"}
            </strong>
          </div>
        </aside>
      </section>

      <section className="grid gap-5 lg:grid-cols-[minmax(320px,0.9fr)_minmax(420px,1.1fr)]">
        <section className="glass-card p-5">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold text-moss-900">Inputs</h2>
                <p className="text-sm text-moss-600">
                  Use shipped data samples or upload your own document.
                </p>
              </div>
              {selectedSample ? (
                <span
                  className={`rounded-full px-3 py-1 text-[0.72rem] uppercase tracking-[0.16em] ${
                    selectedSample.difficulty === "bad"
                      ? "bg-ember-100 text-ember-700"
                      : "bg-moss-100 text-moss-700"
                  }`}
                >
                  {selectedSample.difficulty}
                </span>
              ) : null}
            </div>

            <label className="block">
              <span className="mb-2 block text-sm text-moss-700">Sample scenario</span>
              <select
                className="field"
                value={selectedSampleId}
                onChange={(event) => {
                  const sample = samples.find((item) => item.id === event.target.value);
                  if (sample) {
                    applySample(sample);
                  }
                }}
              >
                {samples.map((sample) => (
                  <option key={sample.id} value={sample.id}>
                    {sample.label}
                  </option>
                ))}
              </select>
            </label>

            {selectedSample ? (
              <div className="rounded-2xl border border-moss-900/10 bg-white/50 p-4 text-sm text-moss-700">
                <p className="font-medium text-moss-900">{selectedSample.label}</p>
                <p className="mt-1">{selectedSample.description}</p>
              </div>
            ) : null}

            <div className="rounded-3xl border border-dashed border-moss-400/40 bg-white/45 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  className="rounded-full bg-moss-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-moss-800 disabled:cursor-wait disabled:opacity-75"
                  type="button"
                  onClick={handleLoadSampleResume}
                  disabled={!selectedSampleId || isLoadingSample}
                >
                  {isLoadingSample ? "Loading sample CV..." : "Load Sample CV"}
                </button>
                <span className="text-sm text-moss-700">
                  {fileSourceLabel || "No sample resume loaded yet."}
                </span>
              </div>

              <label className="mt-4 block">
                <span className="mb-2 block text-sm text-moss-700">Upload your own CV</span>
                <input
                  className="field"
                  type="file"
                  name="file"
                  accept=".pdf,.docx,.txt,.md"
                  onChange={(event) => {
                    const file = event.target.files?.[0] || null;
                    setSelectedFile(file);
                    setFileSourceLabel(file?.name || "");
                  }}
                />
              </label>
            </div>

            <label className="block">
              <span className="mb-2 block text-sm text-moss-700">Job title</span>
              <input className="field" value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} />
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-2 block text-sm text-moss-700">Company</span>
                <input
                  className="field"
                  value={companyName}
                  onChange={(event) => setCompanyName(event.target.value)}
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-sm text-moss-700">Location</span>
                <input className="field" value={location} onChange={(event) => setLocation(event.target.value)} />
              </label>
            </div>

            <label className="block">
              <span className="mb-2 block text-sm text-moss-700">Skills CSV</span>
              <input className="field" value={skillsCsv} onChange={(event) => setSkillsCsv(event.target.value)} />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm text-moss-700">Job description</span>
              <textarea
                className="field min-h-56 resize-y"
                rows={10}
                value={jobDescription}
                onChange={(event) => setJobDescription(event.target.value)}
              />
            </label>

            <button
              className="w-full rounded-full bg-gradient-to-r from-moss-700 to-moss-500 px-5 py-3 text-sm font-semibold uppercase tracking-[0.18em] text-white transition hover:from-moss-800 hover:to-moss-600 disabled:cursor-wait disabled:opacity-75"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Running orchestration..." : "Run Analysis"}
            </button>
          </form>
        </section>

        <section className="grid gap-5">
          <section className="glass-card p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold text-moss-900">Outcome</h2>
                <p className="text-sm text-moss-600">
                  Reviewer-facing result with explicit model behavior.
                </p>
                {runInfo ? (
                  <p className="mt-1 text-xs uppercase tracking-[0.16em] text-moss-500">
                    Run {runInfo.run_id}
                  </p>
                ) : null}
              </div>
              {analysis ? (
                <span
                  className={`rounded-full px-3 py-1 text-[0.72rem] uppercase tracking-[0.16em] ${
                    analysis.model_mode === "mock"
                      ? "bg-ember-100 text-ember-700"
                      : "bg-moss-100 text-moss-700"
                  }`}
                >
                  {analysis.model_mode}
                </span>
              ) : null}
            </div>

            {error ? <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p> : null}

            {analysis ? (
              <div className="mt-4 space-y-4">
                <p className="text-sm text-moss-700">{analysis.provider_reason}</p>
                {matchSummary ? (
                  <>
                    <div className="rounded-2xl bg-moss-900 px-4 py-4 text-moss-50">
                      <p className="meta-label text-moss-200">Summary</p>
                      <h3 className="mt-2 text-2xl font-semibold text-white">{matchSummary.headline}</h3>
                      <p className="mt-2 text-sm text-moss-100">{matchSummary.overall_summary}</p>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl border border-moss-900/10 bg-white/55 p-4">
                        <span className="meta-label">Overall fit</span>
                        <strong className="text-lg text-moss-900">{matchSummary.overall_fit_level}</strong>
                      </div>
                      <div className="rounded-2xl border border-moss-900/10 bg-white/55 p-4">
                        <span className="meta-label">Next step</span>
                        <strong className="text-lg text-moss-900">{matchSummary.ideal_next_step}</strong>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="rounded-2xl bg-ember-100 px-4 py-4 text-sm text-ember-700">
                    Matching was skipped because the uploaded document did not validate as a resume.
                  </div>
                )}

                {extractionNotes.length ? (
                  <div className="rounded-2xl border border-moss-900/10 bg-white/55 p-4">
                    <span className="meta-label">Extraction notes</span>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-moss-700">
                      {extractionNotes.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="mt-4 text-sm text-moss-700">
                Run a sample or uploaded CV through the flow to populate the orchestration result.
              </p>
            )}
          </section>

          <section className="glass-card p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold text-moss-900">Trace</h2>
                <p className="text-sm text-moss-600">Live grouped stepper with revealable event details.</p>
              </div>
              <span className="rounded-full bg-moss-100 px-3 py-1 text-[0.72rem] uppercase tracking-[0.16em] text-moss-700">
                {progressEvents.length || trace.length} events
              </span>
            </div>

            <div className="mt-4 space-y-3">
              {stageGroups.length ? (
                stageGroups.map((group) => (
                  <article
                    className={`rounded-2xl border p-4 ${
                      group.hasFailure
                        ? "border-red-200 bg-red-50/70"
                        : group.hasGuardrailFailure
                          ? "border-ember-200 bg-ember-100/50"
                          : "border-moss-900/10 bg-white/55"
                    }`}
                    key={group.stage}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="text-lg font-semibold capitalize text-moss-900">{formatStage(group.stage)}</h3>
                        <p className="mt-1 text-sm text-moss-600">
                          {group.latestEvent?.message || group.latestEvent?.label || formatEventType(group.latestEvent?.type || "step")}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <span className="rounded-full bg-white/80 px-3 py-1 text-[0.68rem] uppercase tracking-[0.14em] text-moss-700">
                          {group.events.length} events
                        </span>
                        {group.llmCallCount ? (
                          <span className="rounded-full bg-white/80 px-3 py-1 text-[0.68rem] uppercase tracking-[0.14em] text-moss-700">
                            {group.llmCallCount} model calls
                          </span>
                        ) : null}
                        {group.totalTokens ? (
                          <span className="rounded-full bg-white/80 px-3 py-1 text-[0.68rem] uppercase tracking-[0.14em] text-moss-700">
                            {group.totalTokens} tokens
                          </span>
                        ) : null}
                        {group.totalCost > 0 ? (
                          <span className="rounded-full bg-white/80 px-3 py-1 text-[0.68rem] uppercase tracking-[0.14em] text-moss-700">
                            {formatCurrency(group.totalCost)}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {group.events.map((event) => (
                        <StepPill event={event} key={`${event.sequence}-${event.type}`} />
                      ))}
                    </div>
                  </article>
                ))
              ) : trace.length ? (
                trace.map((step) => (
                  <article
                    className="rounded-2xl border border-moss-900/10 bg-white/55 p-4"
                    key={`${step.step}-${step.started_at}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <strong className="text-moss-900">{step.step}</strong>
                      <span
                        className={`rounded-full px-3 py-1 text-[0.68rem] uppercase tracking-[0.16em] ${
                          step.status === "skipped"
                            ? "bg-ember-100 text-ember-700"
                            : "bg-moss-100 text-moss-700"
                        }`}
                      >
                        {step.status}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-moss-600">{step.agent}</p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <div>
                        <span className="meta-label">Input contract</span>
                        <p className="mt-1 text-sm text-moss-800">{step.input_contract.summary}</p>
                      </div>
                      <div>
                        <span className="meta-label">Output contract</span>
                        <p className="mt-1 text-sm text-moss-800">{step.output_contract.summary}</p>
                      </div>
                    </div>
                    <p className="mt-3 text-sm text-moss-700">
                      <span className="font-medium text-moss-900">Validation:</span>{" "}
                      {step.validation.ok ? "ok" : "attention"} {step.validation.message}
                    </p>
                  </article>
                ))
              ) : (
                <p className="text-sm text-moss-700">No trace yet.</p>
              )}
            </div>
          </section>
        </section>
      </section>

      <section className="glass-card mt-5 p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-moss-900">Structured Payload</h2>
            <p className="text-sm text-moss-600">
              Useful during review to show contracts and fallback behavior directly.
            </p>
          </div>
          {analysis?.matching?.jd_match_overview?.header?.overall_match ? (
            <span className="rounded-full bg-moss-900 px-3 py-1 text-[0.72rem] uppercase tracking-[0.16em] text-white">
              {analysis.matching.jd_match_overview.header.overall_match.percent}% match
            </span>
          ) : null}
        </div>
        <pre className="mt-4 overflow-auto rounded-3xl bg-moss-900 p-4 text-xs leading-6 text-moss-50">
          {analysis ? JSON.stringify(analysis, null, 2) : "Waiting for orchestration output."}
        </pre>
      </section>
    </main>
  );
}
