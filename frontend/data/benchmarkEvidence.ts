export type BenchmarkEvidence = {
  category: string;
  versions: string[];
  meaning: string;
  boundary: string;
};

const internalBoundary = "Internal/local evidence only. Not external certification.";

export const benchmarkEvidence: BenchmarkEvidence[] = [
  {
    category: "Reconstruction tests",
    versions: ["V0.36 Trust Suite - PASS", "V0.37 Realistic Memory Benchmark - PASS", "V0.50 Whole Core Truth Gauntlet - PASS"],
    meaning: "Internal checks exercise whether PRMR can reconstruct useful current state from stored continuity evidence.",
    boundary: "Internal/local reconstruction evidence only. Not real-world validation."
  },
  {
    category: "Compression / token-cost tests",
    versions: ["V0.41 Token Tax / Cost War - PASS", "V0.41.2 Hard Token Tax / Cost War - PASS", "V0.41.3 Hard Token Tax Integrity Audit - PASS"],
    meaning: "Internal checks compare continuity compression and token/cost behavior against heavier replay-style baselines.",
    boundary: internalBoundary
  },
  {
    category: "Baseline comparisons",
    versions: ["V0.38.1 Baseline War Anti-Leak - PASS", "V0.38.2 Baseline War Integrity Audit - PASS", "V0.46 Fraud Baseline War - PASS"],
    meaning: "Internal comparisons test PRMR against baseline approaches and guard against anti-leak or easy-row shortcuts.",
    boundary: internalBoundary
  },
  {
    category: "Messy memory trials",
    versions: ["V0.37 Realistic Memory Benchmark - PASS", "V0.39 Adversarial Memory Trial - PASS", "V0.39.1 Adversarial Integrity + Fairness Audit - PASS"],
    meaning: "Internal trials use noisy or adversarial memory situations where raw storage alone can become misleading.",
    boundary: internalBoundary
  },
  {
    category: "Security / client isolation checks",
    versions: ["V0.36.3 Security + Client Isolation - PASS", "V0.43 Security Killbox - PASS", "V0.52.2 Alpha API Sandbox Integrity - PASS"],
    meaning: "Internal checks show that local sandbox keys, vaults, ownership, and public/private report boundaries are enforced in controlled tests.",
    boundary: "Internal/local evidence only. Not external security certification."
  },
  {
    category: "API sandbox checks",
    versions: ["V0.52.0 Alpha API Contract - PASS", "V0.52.1 Alpha API Sandbox - PASS", "V0.52.2 Alpha API Sandbox Integrity - PASS"],
    meaning: "Internal checks cover the controlled-alpha API contract shape, local sandbox behavior, key rotation, revocation, ownership, and usage boundaries.",
    boundary: "Local sandbox evidence only. Not a hosted API."
  },
  {
    category: "Fraud/risk continuity simulations",
    versions: ["V0.45 Fraud Continuity Simulator - PASS", "V0.46 Fraud Baseline War - PASS", "V0.49 Fraud Track Master Gauntlet - PASS"],
    meaning: "Internal synthetic fraud/risk simulations test continuity reasoning as one proof domain, without final accusations or punitive decisions.",
    boundary: "Synthetic/local evidence only. Not bank approval or real-world fraud validation."
  },
  {
    category: "Explainability checks",
    versions: ["V0.47 Fraud Explainability Report - PASS", "V0.47.1 Explainability Integrity Audit - PASS", "V0.47.2 Explainability Report Leak Scan - PASS"],
    meaning: "Internal checks test whether explanations stay consistent with continuity evidence and avoid leaking restricted details.",
    boundary: internalBoundary
  },
  {
    category: "Human-harm reduction checks",
    versions: ["V0.48 Human Harm Reduction Test - PASS", "V0.48.1 Human Harm Integrity Audit - PASS", "V0.48.2 Human Harm Report Leak Scan - PASS"],
    meaning: "Internal checks test review-oriented action boundaries and safer language around sensitive outcomes.",
    boundary: internalBoundary
  },
  {
    category: "Public/private report hygiene",
    versions: ["V0.50 Whole Core Truth Gauntlet - PASS", "V0.52.2 Sandbox Integrity Audit - PASS", "V0.54.8 Kimi Section Fidelity - PASS"],
    meaning: "Internal checks scan public outputs for restricted terms, private trace leakage, and claim-safety issues.",
    boundary: internalBoundary
  },
  {
    category: "Whole-core truth gauntlet",
    versions: ["V0.50 Whole Core Truth Gauntlet - PASS"],
    meaning: "The repo-level internal truth gauntlet reruns discovered run/audit scripts and checks for stale reports, fake passes, private-term leaks, and obvious forced-pass patterns.",
    boundary: "Internal repo truth lock only. Not production certification."
  },
  {
    category: "Demo replay evidence",
    versions: ["V0.53 Local Live Demo Harness - PASS", "V0.53.1 Demo Replay Pack - PASS"],
    meaning: "Local synthetic demos show the controlled-alpha flow for agent memory, support history, and fraud/risk continuity examples.",
    boundary: "Local demo evidence only. Synthetic/demo data only."
  }
];
