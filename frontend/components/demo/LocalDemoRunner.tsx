"use client";

import { useEffect, useMemo, useState } from "react";
import { ContinuityPacketCard } from "@/components/demo/ContinuityPacketCard";
import { DenialPathCard } from "@/components/demo/DenialPathCard";
import { EventsSummaryCard } from "@/components/demo/EventsSummaryCard";
import { ExplanationCard } from "@/components/demo/ExplanationCard";
import { LeastHarmActionCard } from "@/components/demo/LeastHarmActionCard";
import { ReconstructionCard } from "@/components/demo/ReconstructionCard";
import { ReportPreviewCard } from "@/components/demo/ReportPreviewCard";
import { ScenarioSelector } from "@/components/demo/ScenarioSelector";
import { LabFrame } from "@/components/visual/LabFrame";
import { demoScenarios } from "@/data/demoData";
import type { ConnectedDemoResponse, DemoScenarioOption } from "@/data/demoConnection";

const fallbackScenarios: DemoScenarioOption[] = demoScenarios.map((scenario) => ({
  scenario_id: scenario.id,
  scenario_name: scenario.name,
  description: scenario.description
}));

export function LocalDemoRunner() {
  const [scenarios, setScenarios] = useState<DemoScenarioOption[]>(fallbackScenarios);
  const [selectedId, setSelectedId] = useState(fallbackScenarios[0]?.scenario_id || "ai_agent_memory");
  const [result, setResult] = useState<ConnectedDemoResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedScenario = useMemo(
    () => scenarios.find((scenario) => scenario.scenario_id === selectedId) || scenarios[0],
    [scenarios, selectedId]
  );

  useEffect(() => {
    let cancelled = false;

    async function loadScenarios() {
      try {
        const response = await fetch("/api/demo/scenarios", { cache: "no-store" });
        const payload = await response.json();
        if (!cancelled && payload.status === "ok" && Array.isArray(payload.scenarios)) {
          setScenarios(payload.scenarios);
          if (payload.scenarios[0]?.scenario_id) {
            setSelectedId((current) => current || payload.scenarios[0].scenario_id);
          }
        }
      } catch {
        if (!cancelled) {
          setError("Scenario route unavailable. Static synthetic scenarios are still shown, but the local bridge should be checked.");
        }
      }
    }

    loadScenarios();
    return () => {
      cancelled = true;
    };
  }, []);

  async function runDemo() {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch("/api/demo/run", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ scenario_id: selectedId })
      });
      const payload = await response.json();

      if (!response.ok || payload.status !== "ok") {
        throw new Error(payload.error?.message || "Local demo run failed.");
      }

      setResult(payload as ConnectedDemoResponse);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Local demo run failed.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="relative mx-auto max-w-[1400px] px-6 pb-24 pt-32">
      <ScenarioSelector scenarios={scenarios} selectedId={selectedId} onSelect={setSelectedId} disabled={isLoading} />

      <LabFrame className="mt-6 p-6">
        <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Local proxy run</p>
            <h2 className="mt-2 font-display text-3xl text-mist">{selectedScenario?.scenario_name || "Synthetic demo"}</h2>
            <p className="mt-3 text-sm leading-6 text-mist/62">
              Synthetic data only. Local controlled-alpha demo. Not hosted production. The flow shows raw events becoming
              a continuity packet, reconstructed state, a public-safe explanation, a report preview, and safe denial paths.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row lg:flex-col">
            <button className="liquid-glass-btn" disabled={isLoading} onClick={runDemo} type="button">
              {isLoading ? "Running Local Demo" : "Run Local Demo"}
            </button>
            <a className="liquid-glass-btn" href="/book-demo">
              Book a Demo
            </a>
          </div>
        </div>
      </LabFrame>

      {error ? (
        <LabFrame className="mt-6 border-red-200/30 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/64">Error state</p>
          <p className="mt-3 text-sm leading-6 text-mist/70">{error}</p>
        </LabFrame>
      ) : null}

      {isLoading ? (
        <LabFrame className="mt-6 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/64">Loading state</p>
          <p className="mt-3 text-sm leading-6 text-mist/70">Running the local server-side demo bridge.</p>
        </LabFrame>
      ) : null}

      {result ? (
        <>
          <LabFrame className="mt-6 p-6">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/64">Boundary</p>
            <p className="mt-3 text-sm leading-6 text-mist/72">{result.boundary}</p>
          </LabFrame>
          <section className="grid gap-4 py-8 lg:grid-cols-2">
            <EventsSummaryCard events={result.events_summary} />
            <ContinuityPacketCard packet={result.continuity_packet} />
            <ReconstructionCard reconstruction={result.reconstruction} />
            <ExplanationCard explanation={result.explanation} />
            <LeastHarmActionCard action={result.least_harm_action} />
            <ReportPreviewCard report={result.report_preview} />
            <DenialPathCard denialPath={result.denial_path} />
          </section>
        </>
      ) : null}
    </div>
  );
}
