export interface Env {
  // Secret set via: wrangler secret put GITHUB_TOKEN
  GITHUB_TOKEN?: string;

  // Optional secret to protect manual /trigger endpoint
  TRIGGER_SECRET?: string;

  // Config vars defined in wrangler.toml
  GITHUB_REPO?: string;
  WORKFLOW_FILE?: string;
  WORKFLOW_REF?: string;
}

interface TriggerResult {
  ok: boolean;
  status: number;
  message: string;
  source: string;
  timestamp: string;
  repo: string;
  workflow: string;
  ref: string;
}

export default {
  /**
   * Hourly Cron Trigger handler
   * Cloudflare fires this automatically per the `[triggers] crons` configuration.
   */
  async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    const cronExpr = event.cron || "42 * * * *";
    console.log(`[cron] Scheduled trigger fired at ${new Date(event.scheduledTime).toISOString()} (cron: ${cronExpr})`);
    
    ctx.waitUntil(
      triggerGitHubWorkflow(env, `cron:${cronExpr}`).then(res => {
        if (!res.ok) {
          console.error(`[cron] GitHub workflow dispatch failed (status ${res.status}): ${res.message}`);
        } else {
          console.log(`[cron] Successfully dispatched GitHub Actions workflow: ${res.repo}@${res.ref} -> ${res.workflow}`);
        }
      })
    );
  },

  /**
   * HTTP Fetch handler
   * Supports manual triggers and status inspection via browser or curl.
   */
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    // Health / Status endpoint
    if (path === "/" || path === "/status" || path === "/health") {
      const repo = env.GITHUB_REPO || "ianchanning/hn";
      const workflow = env.WORKFLOW_FILE || "hn-observatory-pages.yml";
      const ref = env.WORKFLOW_REF || "main";
      const hasToken = Boolean(env.GITHUB_TOKEN && env.GITHUB_TOKEN.length > 5);

      return jsonResponse({
        service: "hn-observatory-scheduler",
        status: hasToken ? "ready" : "needs_configuration",
        has_github_token: hasToken,
        target_repo: repo,
        workflow_file: workflow,
        workflow_ref: ref,
        schedule: "42 * * * * (hourly at :42 UTC)",
        help: hasToken
          ? "To manually trigger: POST or GET /trigger"
          : "Missing GITHUB_TOKEN. Run: wrangler secret put GITHUB_TOKEN",
        endpoints: {
          status: "GET /status",
          trigger: "POST /trigger (or GET /trigger)",
        },
      });
    }

    // Manual Trigger endpoint
    if (path === "/trigger") {
      if (request.method !== "POST" && request.method !== "GET") {
        return jsonResponse({ error: "Method not allowed. Use POST or GET." }, 405);
      }

      // Check optional trigger secret protection
      if (env.TRIGGER_SECRET) {
        const authHeader = request.headers.get("Authorization") || "";
        const bearer = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";
        const querySecret = url.searchParams.get("secret") || "";
        if (bearer !== env.TRIGGER_SECRET && querySecret !== env.TRIGGER_SECRET) {
          return jsonResponse({ error: "Unauthorized. Invalid or missing TRIGGER_SECRET." }, 401);
        }
      }

      const result = await triggerGitHubWorkflow(env, "manual:http");
      return jsonResponse(result, result.ok ? 200 : 502);
    }

    return jsonResponse({ error: "Not found", path }, 404);
  },
};

/**
 * Dispatches the GitHub Actions workflow using GitHub REST API.
 */
async function triggerGitHubWorkflow(env: Env, source: string): Promise<TriggerResult> {
  const repo = env.GITHUB_REPO || "ianchanning/hn";
  const workflow = env.WORKFLOW_FILE || "hn-observatory-pages.yml";
  const ref = env.WORKFLOW_REF || "main";
  const token = env.GITHUB_TOKEN;
  const timestamp = new Date().toISOString();

  if (!token) {
    const msg = "GITHUB_TOKEN is not set. Run: wrangler secret put GITHUB_TOKEN";
    console.error(msg);
    return {
      ok: false,
      status: 500,
      message: msg,
      source,
      timestamp,
      repo,
      workflow,
      ref,
    };
  }

  const endpoint = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`;
  const payload = {
    ref,
    inputs: {
      target: "frontpage",
      frontpage_limit: "30",
      refresh: "true",
    },
  };

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "cloudflare-worker-hn-observatory-scheduler",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    // 204 No Content indicates successful workflow dispatch
    const ok = response.status === 204 || response.ok;
    const bodyText = await response.text();

    let message = ok
      ? "Successfully dispatched workflow"
      : `GitHub API error: ${bodyText || response.statusText}`;

    return {
      ok,
      status: response.status,
      message,
      source,
      timestamp,
      repo,
      workflow,
      ref,
    };
  } catch (err: any) {
    const errMsg = err?.message || String(err);
    console.error(`[trigger] Network or fetch error: ${errMsg}`);
    return {
      ok: false,
      status: 500,
      message: `Fetch failed: ${errMsg}`,
      source,
      timestamp,
      repo,
      workflow,
      ref,
    };
  }
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data, null, 2) + "\n", {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
