# PRMR V0.56 Founder Demo Recording Script

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.56

## Recording Goal

Record a clean 2-5 minute founder walkthrough that feels calm, technical, and credible. The demo should show a real local flow without overstating what has been proven.

## Opening Line

PRMR Memory Core is continuity infrastructure for AI systems and organisations. It helps systems preserve what changed, what matters, what became stale, and what needs review.

## Talk Track

### 1. Set The Problem

Modern systems store a lot of information: logs, chats, vectors, summaries, tickets, documents, user events, support history, and transaction-like activity.

But storage alone does not preserve continuity.

Systems can lose track of what changed, what stayed true, what became stale, what evidence still matters, and what should happen next.

That is the continuity gap PRMR Memory Core is built around.

### 2. State The Product Truth

PRMR Memory Core is not an AI model.

It sits beside AI systems, databases, vector stores, and SaaS tools as a continuity layer. The goal is not to replace storage or reasoning. The goal is to preserve a smaller, safer continuity packet that a system can use before the next action.

### 3. Open The Local Demo

I am going to show the local controlled-alpha demo.

This is running on localhost. The data is synthetic. The frontend is connected to a local server-side demo bridge, which returns public-safe demo output.

Open:

```text
http://localhost:3000/demo
```

Point out the scenario selector.

The demo includes three synthetic scenarios:

- AI agent memory continuity
- Customer support/user-history continuity
- Fraud/risk continuity sandbox

For this walkthrough, select one scenario and click `Run Local Demo`.

### 4. Explain What Just Happened

When I click this button, the browser does not call PRMR core directly.

The browser calls a Next.js proxy route. That route runs server-side and calls a local PRMR demo bridge. The bridge uses synthetic fixture data and returns a public-safe JSON response.

The browser receives the visible demo result only.

### 5. Walk Through The Result Cards

First, these are the synthetic events.

They show a small activity history moving from one state to another. The point is not the raw volume of data. The point is the shape of change over time.

Next is the continuity packet.

This packet captures the current state, active signals, stale signals, evidence summary, and a continuity summary. This is the compact state PRMR is designed to preserve.

Next is reconstructed state.

This shows that the current state can be reconstructed from the continuity flow instead of replaying every raw event in the interface.

Next is the public-safe explanation.

This explanation is intentionally cautious. It avoids private diagnostic detail and avoids final certainty. It is written for review, not accusation.

Next is the least-harm action.

The action is proportionate and review-oriented. It does not make a final automated decision. It suggests a safe next step such as requesting evidence or human review.

Next is the report preview.

This is a public-safe report preview. It is not the private diagnostic report.

Finally, this is the denial path.

The demo shows that wrong-key and cross-client access attempts are denied in the local sandbox flow. The frontend only receives the public-safe denial outcome, not secret material or private diagnostic packets.

### 6. Evidence Summary

This demo is built on internal/local evidence from the repo:

- V0.50 whole-core truth gauntlet: PASS
- V0.52 local alpha API sandbox: PASS
- V0.52.2 sandbox integrity audit: PASS
- V0.53.1 replay pack: PASS
- V0.55 frontend-to-demo-backend connection: PASS

Those are internal/local checks. They help us keep the demo honest, but they are not external certification.

### 7. Boundary Statement

This is local controlled-alpha evidence using synthetic data. It is not hosted production, not bank approval, not compliance approval, not legal approval, not external security certification, and not real-world validation.

### 8. Closing CTA

I am opening controlled alpha conversations with AI builders, SaaS teams, and organisations dealing with messy context and continuity problems.

If your system stores a lot of history but struggles to preserve what changed, what matters, and what needs review, that is the conversation PRMR Memory Core is built for.

## Short Version

PRMR Memory Core is continuity infrastructure for AI systems and organisations. It is not an AI model. It sits beside existing systems and turns messy event history into compact continuity packets that preserve current state, active signals, stale signals, evidence summary, public-safe explanation, and review-oriented next steps.

This local demo uses synthetic data only. It is controlled-alpha evidence, not hosted production or external validation.

## Delivery Notes

- Speak slowly.
- Let each card stay on screen for a moment.
- Do not rush the boundary statement.
- Keep the tone technical and grounded.
- If recording for LinkedIn, use the short version and keep the walkthrough near two minutes.
- If recording for a buyer conversation or pitch competition, use the full version and keep the walkthrough under five minutes.
