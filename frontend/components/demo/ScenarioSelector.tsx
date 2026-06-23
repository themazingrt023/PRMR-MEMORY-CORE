"use client";

import { LabFrame } from "@/components/visual/LabFrame";
import type { DemoScenario } from "@/data/demoData";
import type { DemoScenarioOption } from "@/data/demoConnection";

export function ScenarioSelector({
  scenarios,
  selectedId,
  onSelect,
  disabled = false
}: {
  scenarios: Array<DemoScenario | DemoScenarioOption>;
  selectedId: string;
  onSelect?: (scenarioId: string) => void;
  disabled?: boolean;
}) {
  return (
    <LabFrame className="p-6">
      <p className="font-mono text-sm uppercase tracking-[0.28em] text-silver/64">Synthetic demo scenarios</p>
      <h1 className="mt-3 font-display text-4xl text-mist">Local replay preview</h1>
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        {scenarios.map((scenario) => {
          const scenarioId = "scenario_id" in scenario ? scenario.scenario_id : scenario.id;
          const scenarioName = "scenario_name" in scenario ? scenario.scenario_name : scenario.name;
          const isSelected = scenarioId === selectedId;

          return (
          <button
            className={`silver-hover border p-4 text-left transition ${
              isSelected ? "border-silver/60 bg-white/[0.055]" : "border-silver/16"
            }`}
            disabled={disabled}
            key={scenarioId}
            onClick={() => onSelect?.(scenarioId)}
            type="button"
          >
            <h2 className="font-display text-xl text-silver">{scenarioName}</h2>
            <p className="mt-2 text-sm leading-6 text-mist/70">{scenario.description}</p>
          </button>
          );
        })}
      </div>
    </LabFrame>
  );
}
