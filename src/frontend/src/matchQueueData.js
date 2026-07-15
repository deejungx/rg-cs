/**
 * @typedef {"pass" | "review_later" | "shortlist" | null} MatchDecision
 * @typedef {{ label: string, met: number, total: number }} RequirementCoverage
 * @typedef {{ text: string, requirement: string, icon: "code" | "cloud" | "architecture" | "database" | "delivery" }} MatchEvidence
 * @typedef {{ id: string, identity: { name: string, initials: string, role: string, location: string, workMode: string }, summary: string, match: { score: number, confidence: "High confidence" | "Medium confidence" }, coverage: RequirementCoverage[], evidence: MatchEvidence[], watchOuts: string[], unknowns: string[], decisionStatus: MatchDecision }} CandidateMatch
 */

/** @type {CandidateMatch[]} */
export const candidateMatches = [
  {
    id: "candidate-anisha-sharma",
    identity: {
      name: "Anisha Sharma",
      initials: "AS",
      role: "Senior Python Engineer",
      location: "Kathmandu",
      workMode: "Remote",
    },
    summary: "Backend engineer focused on Python services, cloud infrastructure, and high-volume platform systems.",
    match: { score: 87, confidence: "High confidence" },
    coverage: [
      { label: "Must-have skills", met: 8, total: 10 },
      { label: "Experience", met: 6, total: 7 },
      { label: "Tools & frameworks", met: 6, total: 8 },
      { label: "Education", met: 1, total: 1 },
    ],
    evidence: [
      { text: "Strong Python & Django expertise with 7+ years building scalable APIs and microservices.", requirement: "Core stack", icon: "code" },
      { text: "Extensive AWS experience (ECS, Lambda, RDS, S3) and demonstrated performance at scale.", requirement: "Cloud", icon: "cloud" },
      { text: "Proven backend systems and design experience across multiple production platforms.", requirement: "System design", icon: "architecture" },
    ],
    watchOuts: ["Limited exposure to Kubernetes in production", "No recent experience with Go or gRPC"],
    unknowns: ["Production on-call ownership is not documented", "Current notice period has not been confirmed"],
    decisionStatus: null,
  },
  {
    id: "candidate-rohan-thapa",
    identity: { name: "Rohan Thapa", initials: "RT", role: "Backend Platform Engineer", location: "Lalitpur", workMode: "Hybrid" },
    summary: "Platform engineer with strong distributed-systems fundamentals and production Kubernetes ownership.",
    match: { score: 84, confidence: "High confidence" },
    coverage: [
      { label: "Must-have skills", met: 8, total: 10 },
      { label: "Experience", met: 5, total: 7 },
      { label: "Tools & frameworks", met: 7, total: 8 },
      { label: "Education", met: 1, total: 1 },
    ],
    evidence: [
      { text: "Six years delivering Python services with FastAPI and PostgreSQL in production.", requirement: "Core stack", icon: "code" },
      { text: "Owned Kubernetes deployments and AWS infrastructure for a multi-tenant SaaS platform.", requirement: "Infrastructure", icon: "cloud" },
      { text: "Documented improvements to queue throughput and database query latency.", requirement: "Scale", icon: "database" },
    ],
    watchOuts: ["Django experience is older than three years", "No evidence of gRPC ownership"],
    unknowns: ["Team leadership scope is unclear"],
    decisionStatus: null,
  },
  {
    id: "candidate-samira-karki",
    identity: { name: "Samira Karki", initials: "SK", role: "Senior Software Engineer", location: "Pokhara", workMode: "Remote" },
    summary: "Product-minded backend engineer experienced in reliable APIs, mentoring, and cloud delivery.",
    match: { score: 81, confidence: "High confidence" },
    coverage: [
      { label: "Must-have skills", met: 7, total: 10 },
      { label: "Experience", met: 7, total: 7 },
      { label: "Tools & frameworks", met: 6, total: 8 },
      { label: "Education", met: 1, total: 1 },
    ],
    evidence: [
      { text: "Eight years of Python development, including five years with Django REST Framework.", requirement: "Core stack", icon: "code" },
      { text: "Led backend design reviews and mentored four engineers on service reliability.", requirement: "Leadership", icon: "architecture" },
      { text: "Implemented CI/CD controls and observability for AWS-hosted services.", requirement: "Delivery", icon: "delivery" },
    ],
    watchOuts: ["No production Kubernetes evidence", "Limited detail on systems above 10k requests per minute"],
    unknowns: ["Go proficiency is not stated"],
    decisionStatus: null,
  },
];

export const initialRemainingCount = 42;
