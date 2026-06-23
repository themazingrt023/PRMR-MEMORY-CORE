import { spawn } from "node:child_process";
import path from "node:path";

type BridgeCommand = "health" | "report" | "run" | "scenarios";

export type LocalBridgeResult = Record<string, unknown>;

const REPO_ROOT = path.resolve(process.cwd(), "..");
const BRIDGE_PATH = path.join(REPO_ROOT, "examples", "demo_v055_frontend_bridge.py");

export async function callLocalDemoBridge(command: BridgeCommand, scenarioId?: string): Promise<LocalBridgeResult> {
  const python = process.env.PRMR_LOCAL_DEMO_PYTHON || "python";
  const args = [BRIDGE_PATH, command];
  if (scenarioId) args.push(scenarioId);

  return new Promise((resolve, reject) => {
    const child = spawn(python, args, {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
        PYTHONUTF8: "1"
      },
      stdio: ["ignore", "pipe", "pipe"]
    });

    let stdout = "";
    let stderr = "";

    child.stdout.setEncoding("utf-8");
    child.stderr.setEncoding("utf-8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });

    child.on("error", reject);
    child.on("close", (code) => {
      try {
        const payload = JSON.parse(stdout) as LocalBridgeResult;
        if (code === 0) {
          resolve(payload);
          return;
        }
        reject(new Error(String(payload.error || stderr || "Local demo bridge failed.")));
      } catch (error) {
        reject(error instanceof Error ? error : new Error("Local demo bridge returned invalid JSON."));
      }
    });
  });
}

export function publicBridgeError(message = "Local demo bridge unavailable.") {
  return {
    status: "error",
    synthetic_only: true,
    boundary: "Synthetic data only. Local controlled-alpha demo. Not hosted production.",
    error: {
      code: "local_bridge_unavailable",
      message
    }
  };
}
