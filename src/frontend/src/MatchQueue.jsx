import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  AlertTriangle,
  ArrowLeft,
  Bookmark,
  Check,
  ChevronDown,
  CircleHelp,
  Cloud,
  Code2,
  Database,
  Filter,
  GitBranch,
  Layers3,
  MapPin,
  RotateCcw,
  SlidersHorizontal,
  Sparkles,
  UserMinus,
  Users,
  X,
} from "lucide-react";
import { candidateMatches, initialRemainingCount } from "./matchQueueData";

const evidenceIcons = { code: Code2, cloud: Cloud, architecture: GitBranch, database: Database, delivery: Layers3 };
const decisionLabels = { pass: "Passed", review_later: "Saved for later", shortlist: "Shortlisted" };

function Filters({ onClose }) {
  const [filters, setFilters] = useState({ job: "Senior Backend Engineer", location: "Any location", experience: "Any experience", skills: "All skills", availability: "Any availability" });
  const setFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  const clear = () => setFilters({ job: "Senior Backend Engineer", location: "Any location", experience: "Any experience", skills: "All skills", availability: "Any availability" });
  return (
    <div className="queue-filters-inner">
      <div className="queue-section-heading">
        <div><SlidersHorizontal size={16} aria-hidden="true" /><h2>Filters</h2></div>
        <div className="filter-heading-actions">
          <button className="text-button" type="button" onClick={clear}>Clear all</button>
          {onClose ? <button className="icon-button filter-close" type="button" aria-label="Close filters" onClick={onClose}><X size={18} /></button> : null}
        </div>
      </div>
      <div className="filter-fields">
        <label><span>Job opening</span><select value={filters.job} onChange={(event) => setFilter("job", event.target.value)}><option>Senior Backend Engineer</option><option>Frontend Engineer</option><option>Product Designer</option></select><ChevronDown size={15} aria-hidden="true" /></label>
        <label><span>Location</span><select value={filters.location} onChange={(event) => setFilter("location", event.target.value)}><option>Any location</option><option>Kathmandu</option><option>Lalitpur</option><option>Remote</option></select><ChevronDown size={15} aria-hidden="true" /></label>
        <label><span>Experience</span><select value={filters.experience} onChange={(event) => setFilter("experience", event.target.value)}><option>Any experience</option><option>5–7 years</option><option>8+ years</option></select><ChevronDown size={15} aria-hidden="true" /></label>
        <label><span>Skills</span><select value={filters.skills} onChange={(event) => setFilter("skills", event.target.value)}><option>All skills</option><option>Python</option><option>AWS</option><option>Kubernetes</option></select><ChevronDown size={15} aria-hidden="true" /></label>
        <label><span>Availability</span><select value={filters.availability} onChange={(event) => setFilter("availability", event.target.value)}><option>Any availability</option><option>Immediately</option><option>Within 30 days</option></select><ChevronDown size={15} aria-hidden="true" /></label>
      </div>
    </div>
  );
}

function AnimatedCount({ value }) {
  const previousValue = useRef(value);
  const reduceMotion = useReducedMotion();
  const direction = value >= previousValue.current ? 1 : -1;
  useEffect(() => { previousValue.current = value; }, [value]);
  return <span className="animated-count" aria-label={value}><AnimatePresence initial={false} mode="popLayout" custom={direction}><motion.span key={value} custom={direction} initial={reduceMotion ? false : { y: direction * 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={reduceMotion ? { opacity: 0 } : { y: direction * -12, opacity: 0 }} transition={{ duration: reduceMotion ? 0 : 0.2 }}>{value}</motion.span></AnimatePresence></span>;
}

function QueueStats({ history }) {
  const counts = history.reduce((result, item) => ({ ...result, [item.decision]: result[item.decision] + 1 }), { pass: 0, review_later: 0, shortlist: 0 });
  const stats = [
    { label: "Remaining", value: Math.max(0, initialRemainingCount - history.length), icon: Users, tone: "remaining" },
    { label: "Shortlisted", value: counts.shortlist, icon: Check, tone: "shortlisted" },
    { label: "Review later", value: counts.review_later, icon: Bookmark, tone: "later" },
    { label: "Passed", value: counts.pass, icon: UserMinus, tone: "passed" },
  ];
  return <section className="queue-stats" aria-label="Queue decision totals">{stats.map(({ label, value, icon: Icon, tone }) => <article className={`queue-stat ${tone}`} key={label}><span className="queue-stat-icon"><Icon size={17} aria-hidden="true" /></span><div><AnimatedCount value={value} /><span>{label}</span></div></article>)}</section>;
}

function InsightPanel({ candidate, onOpenAnalysis }) {
  const totalMet = candidate.coverage.reduce((sum, item) => sum + item.met, 0);
  const totalRequirements = candidate.coverage.reduce((sum, item) => sum + item.total, 0);
  return (
    <aside className="insight-panel" aria-labelledby="insight-title">
      <div className="insight-title"><span><Sparkles size={17} aria-hidden="true" /></span><div><p>AI analysis</p><h2 id="insight-title">AI Match Insight</h2></div></div>
      <section className="confidence-block" aria-label={`Match confidence: ${candidate.match.confidence}`}>
        <div><span>Match confidence</span><strong><Check size={14} aria-hidden="true" />{candidate.match.confidence}</strong></div>
        <div className="confidence-track" role="progressbar" aria-label={`Match confidence ${candidate.match.score} percent`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={candidate.match.score}><span style={{ width: `${candidate.match.score}%` }} /></div>
      </section>
      <section className="coverage-section">
        <h3>Requirement coverage</h3>
        <div className="coverage-list">
          {candidate.coverage.map((item) => {
            const percent = Math.round((item.met / item.total) * 100);
            return <div className="coverage-item" key={item.label}><div><span>{item.label}</span><strong>{item.met} / {item.total}</strong></div><div className="coverage-track" role="progressbar" aria-label={`${item.label}: ${item.met} of ${item.total} requirements met`} aria-valuemin="0" aria-valuemax={item.total} aria-valuenow={item.met}><span style={{ width: `${percent}%` }} /></div></div>;
          })}
        </div>
        <div className="coverage-total"><Check size={16} aria-hidden="true" /><span><strong>{totalMet} / {totalRequirements}</strong> requirements met</span></div>
      </section>
      <section className="watchouts"><h3><AlertTriangle size={16} aria-hidden="true" />Watch-outs</h3><ul>{candidate.watchOuts.map((item) => <li key={item}>{item}</li>)}</ul></section>
      <button className="analysis-button" type="button" onClick={onOpenAnalysis}>View full analysis <ArrowLeft className="analysis-arrow" size={16} aria-hidden="true" /></button>
    </aside>
  );
}

function CandidateCard({ candidate, onDecision }) {
  const reduceMotion = useReducedMotion();
  const cardVariants = {
    exit: (decision) => {
      if (reduceMotion) return { opacity: 0 };
      return {
        pass: { x: -180, opacity: 0, rotate: -3 },
        shortlist: { x: 180, opacity: 0, rotate: 3 },
        review_later: { y: -120, opacity: 0, scale: 0.98 },
      }[decision] || { opacity: 0 };
    },
  };
  const handleDragEnd = (_, info) => {
    if (info.offset.y < -90 && Math.abs(info.offset.y) > Math.abs(info.offset.x)) {
      onDecision("review_later");
    } else if (info.offset.x < -110) {
      onDecision("pass");
    } else if (info.offset.x > 110) {
      onDecision("shortlist");
    }
  };
  return (
    <motion.article
      className="candidate-review-card"
      aria-labelledby="candidate-name"
      drag={reduceMotion ? false : true}
      dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
      dragElastic={{ left: 0.28, right: 0.28, top: 0.22, bottom: 0.05 }}
      onDragEnd={handleDragEnd}
      variants={cardVariants}
      initial={reduceMotion ? false : { opacity: 0, y: 12, scale: 0.99 }}
      animate={{ opacity: 1, x: 0, y: 0, rotate: 0, scale: 1 }}
      exit="exit"
      transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 330, damping: 30 }}
      whileDrag={{ cursor: "grabbing", boxShadow: "0 18px 45px rgba(40, 52, 48, 0.14)" }}
    >
      <header className="candidate-header">
        <div className="candidate-identity"><div className="candidate-avatar" aria-hidden="true">{candidate.identity.initials}</div><div><h2 id="candidate-name">{candidate.identity.name}</h2><p>{candidate.identity.role}</p><span><MapPin size={14} aria-hidden="true" />{candidate.identity.location}<i>·</i>{candidate.identity.workMode}</span></div></div>
        <div className="match-score" aria-label={`${candidate.match.score} percent match`}><strong>{candidate.match.score}%</strong><span>Match</span></div>
      </header>
      <section className="why-matched" aria-labelledby="why-matched-title"><div className="why-heading"><span><Sparkles size={16} aria-hidden="true" /></span><div><h3 id="why-matched-title">Why matched</h3><p>Evidence found in the candidate profile</p></div></div><div className="evidence-list">{candidate.evidence.map((evidence) => { const Icon = evidenceIcons[evidence.icon]; return <div className="evidence-item" key={evidence.text}><span className="evidence-icon"><Icon size={17} aria-hidden="true" /></span><p>{evidence.text}</p><span className="requirement-tag">{evidence.requirement}</span></div>; })}</div></section>
      <footer className="decision-footer"><div className="decision-actions"><button className="decision-button pass" type="button" onClick={() => onDecision("pass")}><X size={18} aria-hidden="true" />Pass</button><button className="decision-button later" type="button" onClick={() => onDecision("review_later")}><Bookmark size={17} aria-hidden="true" />Review later</button><button className="decision-button shortlist" type="button" onClick={() => onDecision("shortlist")}><Check size={18} aria-hidden="true" />Shortlist</button></div><p className="interaction-hint"><CircleHelp size={14} aria-hidden="true" />Use arrow keys or buttons to review.</p></footer>
    </motion.article>
  );
}

function AnalysisModal({ candidate, onClose }) {
  const closeRef = useRef(null);
  useEffect(() => { closeRef.current?.focus(); const onKeyDown = (event) => event.key === "Escape" && onClose(); document.addEventListener("keydown", onKeyDown); return () => document.removeEventListener("keydown", onKeyDown); }, [onClose]);
  return <div className="queue-modal-backdrop" role="presentation" onMouseDown={onClose}><div className="queue-modal" role="dialog" aria-modal="true" aria-labelledby="analysis-title" onMouseDown={(event) => event.stopPropagation()}><header><div><span className="eyebrow">Evidence-based assessment</span><h2 id="analysis-title">{candidate.identity.name}: full analysis</h2><p>{candidate.summary}</p></div><button ref={closeRef} className="icon-button" type="button" aria-label="Close full analysis" onClick={onClose}><X size={20} /></button></header><div className="analysis-grid"><section><h3>Supported evidence</h3>{candidate.evidence.map((item) => <article key={item.text}><Check size={16} aria-hidden="true" /><div><strong>{item.requirement}</strong><p>{item.text}</p></div></article>)}</section><section><h3>Unknown or missing</h3>{candidate.unknowns.map((item) => <article key={item}><CircleHelp size={16} aria-hidden="true" /><p>{item}</p></article>)}<h3 className="modal-subheading">Watch-outs</h3>{candidate.watchOuts.map((item) => <article key={item}><AlertTriangle size={16} aria-hidden="true" /><p>{item}</p></article>)}</section></div></div></div>;
}

export default function MatchQueue() {
  const [history, setHistory] = useState([]);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [exitDecision, setExitDecision] = useState("shortlist");
  const [announcement, setAnnouncement] = useState("");
  const [feedback, setFeedback] = useState(null);
  const currentIndex = history.length % candidateMatches.length;
  const candidate = candidateMatches[currentIndex];
  const remaining = Math.max(0, initialRemainingCount - history.length);

  const decide = (decision) => {
    if (!remaining) return;
    setExitDecision(decision);
    setHistory((current) => [...current, { candidateId: candidate.id, decision }]);
    setAnnouncement(`${candidate.identity.name} ${decisionLabels[decision].toLowerCase()}. Next candidate loaded.`);
    setFeedback({ id: Date.now(), decision, message: `${candidate.identity.name} ${decisionLabels[decision].toLowerCase()}` });
  };
  const undo = () => {
    if (!history.length) return;
    const previous = history[history.length - 1];
    setAnnouncement(`Undid ${decisionLabels[previous.decision].toLowerCase()}.`);
    setFeedback({ id: Date.now(), decision: "undo", message: `Undid ${decisionLabels[previous.decision].toLowerCase()}` });
    setHistory((current) => current.slice(0, -1));
  };

  useEffect(() => {
    if (!feedback) return undefined;
    const timer = window.setTimeout(() => setFeedback(null), 1800);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  useEffect(() => {
    const onKeyDown = (event) => {
      const tag = event.target?.tagName;
      if (["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(tag) || event.target?.isContentEditable || analysisOpen || filtersOpen) return;
      const actions = { ArrowLeft: "pass", ArrowRight: "shortlist", ArrowUp: "review_later" };
      if (actions[event.key]) { event.preventDefault(); decide(actions[event.key]); }
      if (event.key === "Enter") { event.preventDefault(); setAnalysisOpen(true); }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  return <section className="match-queue-page" aria-labelledby="match-queue-title">
    <header className="queue-topbar"><div><span className="eyebrow">Candidate review</span><h1 id="match-queue-title">Match Queue</h1></div><div className="queue-toolbar"><button className="toolbar-button filters-trigger" type="button" onClick={() => setFiltersOpen(true)}><Filter size={16} aria-hidden="true" />Filters</button><button className="toolbar-button" type="button" disabled={!history.length} onClick={undo}><RotateCcw size={16} aria-hidden="true" />Undo</button></div></header>
    <QueueStats history={history} />
    <div className="queue-layout"><aside className="queue-filters"><Filters /></aside><main className="queue-main"><AnimatePresence mode="wait" custom={exitDecision}>{remaining ? <CandidateCard key={`${candidate.id}-${history.length}`} candidate={candidate} onDecision={decide} /> : <motion.div className="queue-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}><Check size={24} aria-hidden="true" /><h2>Queue reviewed</h2><p>All candidates in this queue have a decision.</p></motion.div>}</AnimatePresence></main><InsightPanel candidate={candidate} onOpenAnalysis={() => setAnalysisOpen(true)} /></div>
    {filtersOpen ? <div className="filter-drawer-backdrop" role="presentation" onMouseDown={() => setFiltersOpen(false)}><aside className="filter-drawer" aria-label="Candidate filters" onMouseDown={(event) => event.stopPropagation()}><Filters onClose={() => setFiltersOpen(false)} /></aside></div> : null}
    {analysisOpen ? <AnalysisModal candidate={candidate} onClose={() => setAnalysisOpen(false)} /> : null}
    <AnimatePresence>{feedback ? <motion.div className={`decision-feedback ${feedback.decision}`} key={feedback.id} role="status" initial={{ opacity: 0, y: 12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 6 }}><span>{feedback.decision === "undo" ? <RotateCcw size={17} /> : feedback.decision === "pass" ? <X size={18} /> : feedback.decision === "review_later" ? <Bookmark size={17} /> : <Check size={18} />}</span>{feedback.message}</motion.div> : null}</AnimatePresence>
    <p className="sr-only" aria-live="polite">{announcement}</p>
  </section>;
}
