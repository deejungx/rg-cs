import { useEffect, useState } from "react";

const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function parseJson(response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return response.json();
}

export default function App() {
  const [health, setHealth] = useState("loading");
  const [taskInfo, setTaskInfo] = useState(null);
  const [resultInfo, setResultInfo] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${apiBase}/health`)
      .then(parseJson)
      .then((data) => setHealth(data.status))
      .catch((err) => setHealth(`error: ${err.message}`));
  }, []);

  useEffect(() => {
    if (!taskInfo?.task_id) {
      return undefined;
    }

    const poll = window.setInterval(async () => {
      try {
        const data = await fetch(`${apiBase}/api/cv/tasks/${taskInfo.task_id}`).then(parseJson);
        setTaskInfo(data);
        if (data.state === "SUCCESS") {
          setResultInfo(data.result);
          window.clearInterval(poll);
        }
      } catch (err) {
        setError(err.message);
        window.clearInterval(poll);
      }
    }, 2000);

    return () => window.clearInterval(poll);
  }, [taskInfo?.task_id]);

  async function handleExtraction(event) {
    event.preventDefault();
    setError("");
    setResultInfo(null);
    const formData = new FormData(event.currentTarget);
    const response = await fetch(`${apiBase}/api/cv/extract`, {
      method: "POST",
      body: formData,
    });
    const data = await parseJson(response);
    setTaskInfo(data);
  }

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Full-Stack AI Scaffold</p>
          <h1>CV extraction with FastAPI, Celery, and a CrewAI flow.</h1>
          <p className="lede">
            Upload a CV, queue extraction through FastAPI, let the worker run the CrewAI flow,
            and inspect the structured result plus workspace artifacts.
          </p>
        </div>
        <div className="health">
          <span>Backend health</span>
          <strong>{health}</strong>
        </div>
      </section>

      <section className="card">
        <form onSubmit={handleExtraction}>
          <h2>Extract CV</h2>
          <input type="file" name="file" required />
          <button type="submit">Queue Extraction</button>
          <pre>{taskInfo ? JSON.stringify(taskInfo, null, 2) : "No task submitted."}</pre>
        </form>
      </section>

      <section className="card">
        <h2>Results</h2>
        {error ? <p className="error">{error}</p> : null}
        <pre>{resultInfo ? JSON.stringify(resultInfo, null, 2) : "Waiting for job output."}</pre>
      </section>
    </main>
  );
}
