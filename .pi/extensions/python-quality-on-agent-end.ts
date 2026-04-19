import type {
  ExtensionAPI,
  ExtensionContext,
  ExecResult,
} from "@mariozechner/pi-coding-agent";
import { access } from "node:fs/promises";
import { constants } from "node:fs";
import { join } from "node:path";

const QUALITY_STATUS_KEY = "python-quality";
const QUALITY_COMMANDS: Array<{ label: string; command: string; args: string[] }> = [
  {
    label: "ruff check --fix",
    command: "uv",
    args: ["run", "ruff", "check", ".", "--fix"],
  },
  {
    label: "ruff format",
    command: "uv",
    args: ["run", "ruff", "format", "."],
  },
  {
    label: "ty check --fix",
    command: "uv",
    args: ["run", "ty", "check", ".", "--fix"],
  },
];

let runInProgress = false;

async function fileExists(path: string): Promise<boolean> {
  try {
    await access(path, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

async function shouldRunQualityChecks(cwd: string): Promise<boolean> {
  const [hasPyproject, hasUvLock, hasPreCommitConfig] = await Promise.all([
    fileExists(join(cwd, "pyproject.toml")),
    fileExists(join(cwd, "uv.lock")),
    fileExists(join(cwd, ".pre-commit-config.yaml")),
  ]);
  return hasPyproject && hasUvLock && hasPreCommitConfig;
}

function summarizeResult(result: ExecResult): string {
  const text = (result.stderr || result.stdout || "").trim();
  if (!text) return "";
  const lines = text.split(/\r?\n/).slice(-8);
  return lines.join("\n");
}

async function runQualityChecks(reason: string, ctx: ExtensionContext, pi: ExtensionAPI) {
  if (runInProgress) {
    ctx.ui.setStatus(QUALITY_STATUS_KEY, "Quality checks already running");
    return;
  }

  if (!(await shouldRunQualityChecks(ctx.cwd))) {
    ctx.ui.setStatus(QUALITY_STATUS_KEY, "Quality checks skipped (missing uv/python config)");
    return;
  }

  runInProgress = true;
  ctx.ui.setStatus(QUALITY_STATUS_KEY, `Running Python quality checks (${reason})...`);

  try {
    for (const step of QUALITY_COMMANDS) {
      ctx.ui.setStatus(QUALITY_STATUS_KEY, `Running ${step.label} (${reason})...`);
      const result = await pi.exec(step.command, step.args, {
        cwd: ctx.cwd,
        timeout: 120_000,
        signal: ctx.signal,
      });

      if (result.code !== 0) {
        const summary = summarizeResult(result);
        const message = summary
          ? `${step.label} failed during ${reason}\n${summary}`
          : `${step.label} failed during ${reason}`;
        ctx.ui.setStatus(QUALITY_STATUS_KEY, `${step.label} failed`);
        ctx.ui.notify(message, "error");
        return;
      }
    }

    ctx.ui.setStatus(QUALITY_STATUS_KEY, `Python quality checks passed (${reason})`);
    ctx.ui.notify(`Python quality checks passed (${reason})`, "success");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    ctx.ui.setStatus(QUALITY_STATUS_KEY, `Python quality checks errored (${reason})`);
    ctx.ui.notify(`Python quality checks errored (${reason}): ${message}`, "error");
  } finally {
    runInProgress = false;
  }
}

export default function pythonQualityOnAgentEnd(pi: ExtensionAPI) {
  pi.on("agent_end", async (_event, ctx) => {
    await runQualityChecks("agent_end", ctx, pi);
  });

  pi.registerCommand("quality-check", {
    description: "Run project Python quality checks with uv (ruff + ty)",
    handler: async (_args, ctx) => {
      await runQualityChecks("/quality-check", ctx, pi);
    },
  });
}
