# HN Epistemic Observatory — Cloudflare Hourly Scheduler

A lightweight Cloudflare Worker with a Cron Trigger that reliably triggers the GitHub Actions workflow (`hn-observatory-pages.yml`) every hour.

## Why Cloudflare Worker Scheduler?
GitHub Actions native cron triggers (`schedule: - cron: ...`) frequently suffer from queue delays (30–90 minutes late), dropped runs during peak traffic, and automatic deactivation after 60 days of repository inactivity. 

Cloudflare Cron Triggers execute deterministically within milliseconds of the scheduled time and ping GitHub's `workflow_dispatch` API.

---

## Architecture

- **Trigger:** Cloudflare Cron Trigger at minute 15 and 45 every hour (`15,45 * * * *`).
- **Action:** `POST https://api.github.com/repos/ianchanning/hn/actions/workflows/hn-observatory-pages.yml/dispatches`
- **Inputs:** `target=frontpage`, `frontpage_limit=30`, `refresh=true`
- **Manual Trigger:** `GET /trigger` or `POST /trigger` allows instant verification or ad-hoc runs.
- **Status Endpoint:** `GET /status` returns configuration and health.

---

## Setup & Deployment

### 1. Set the GitHub Token Secret
Run inside this directory (or use the helper script):
```bash
/home/ian/Projects/pinboard-reorg/node_modules/.bin/wrangler secret put GITHUB_TOKEN
```
Paste a GitHub Personal Access Token (PAT) with `repo` or `actions:write` permissions.
*(You can also use your current GitHub CLI token: `gh auth token`)*.

### 2. (Optional) Set a Trigger Secret
To protect the public `/trigger` HTTP endpoint from unauthorized calls:
```bash
/home/ian/Projects/pinboard-reorg/node_modules/.bin/wrangler secret put TRIGGER_SECRET
```
When set, requests to `/trigger` must pass `?secret=<value>` or `Authorization: Bearer <value>`.

### 3. Deploy
```bash
/home/ian/Projects/pinboard-reorg/node_modules/.bin/wrangler deploy
```

### 4. Test
```bash
# Check status
curl https://hn-observatory-scheduler.<your-subdomain>.workers.dev/status

# Manually trigger a run
curl -X POST https://hn-observatory-scheduler.<your-subdomain>.workers.dev/trigger

# Watch live execution logs
/home/ian/Projects/pinboard-reorg/node_modules/.bin/wrangler tail
```
