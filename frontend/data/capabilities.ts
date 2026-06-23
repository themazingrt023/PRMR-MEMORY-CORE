export type Capability = {
  slug: string;
  title: string;
  preview: string;
  image: string;
  deeper: string[];
};

export const capabilities: Capability[] = [
  {
    slug: "event-ingestion",
    title: "Event Ingestion",
    preview: "Normalise and stream events into the PRMR pipeline.",
    image: "/visual/usecase-saas.jpg",
    deeper: [
      "Event ingestion is the entry point for continuity. Applications send synthetic or approved events into PRMR so the system can understand what changed rather than treating every record as flat storage.",
      "In the current local shell, this is represented as controlled-alpha contract and demo evidence only. It is not a hosted ingestion service."
    ]
  },
  {
    slug: "continuity-packets",
    title: "Continuity Packets",
    preview: "Compress what changed into a smaller continuity state.",
    image: "/visual/usecase-knowledge.jpg",
    deeper: [
      "Continuity packets preserve current state, active signals, stale signals, evidence, and report boundaries in a smaller shape than raw event replay.",
      "The goal is not to hide history. The goal is to keep the useful state reconstructable without forcing every system to carry every old event into every next step."
    ]
  },
  {
    slug: "state-reconstruction",
    title: "State Reconstruction",
    preview: "Rebuild the current state from continuity rather than replaying everything.",
    image: "/visual/usecase-agent.jpg",
    deeper: [
      "State reconstruction asks what is true enough to carry forward now, based on continuity rather than raw timeline volume.",
      "The current repo evidence covers internal reconstruction tests and local demo flows, not external validation."
    ]
  },
  {
    slug: "stale-signal-handling",
    title: "Stale Signal Handling",
    preview: "Separate what still matters from what should no longer dominate the next step.",
    image: "/visual/usecase-support.jpg",
    deeper: [
      "Stale signal handling keeps old context from overwhelming current reasoning. It marks what should be demoted, reviewed, or kept dormant.",
      "This is especially useful for long-running agents, support histories, research workflows, and case-like systems where old facts can become misleading."
    ]
  },
  {
    slug: "evidence-awareness",
    title: "Evidence Awareness",
    preview: "Track which signals support the current state and which require review.",
    image: "/visual/usecase-legal.jpg",
    deeper: [
      "Evidence awareness links continuity outputs back to supporting signals and review boundaries.",
      "The local product shell keeps public-safe explanations separate from diagnostic detail and does not expose private internals in public UI."
    ]
  },
  {
    slug: "public-safe-explanations",
    title: "Public-Safe Explanations",
    preview: "Generate explanations that avoid private internals and accusation-heavy language.",
    image: "/visual/usecase-education.jpg",
    deeper: [
      "Public-safe explanations are written for shareable contexts. They avoid restricted traces, internal diagnostic wording, and certain-judgment language.",
      "The current evidence is internal/local report hygiene, not legal, compliance, or external review."
    ]
  },
  {
    slug: "least-harm-actions",
    title: "Least-Harm Actions",
    preview: "Suggest review-oriented next actions without final punitive decisions.",
    image: "/visual/usecase-fraud.jpg",
    deeper: [
      "Least-harm actions are bounded next-step labels such as request evidence, human review, protect user, release cleared funds, or keep dormant.",
      "The system does not make final punitive decisions. It preserves review boundaries and keeps human oversight visible."
    ]
  },
  {
    slug: "public-private-reports",
    title: "Public / Private Reports",
    preview: "Separate public-safe summaries from private diagnostic detail.",
    image: "/visual/usecase-custom.jpg",
    deeper: [
      "Public/private report separation keeps public-safe summaries distinct from deeper internal diagnostics.",
      "The frontend shell displays public-safe demo evidence only. Private/internal report material is not exposed in the public UI."
    ]
  }
];

export function getCapability(slug: string) {
  return capabilities.find((capability) => capability.slug === slug);
}
