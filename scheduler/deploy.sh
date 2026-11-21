#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRANGLER="npx wrangler"

if command -v wrangler >/dev/null 2>&1; then
  WRANGLER="wrangler"
elif [ -x "/home/ian/Projects/pinboard-reorg/node_modules/.bin/wrangler" ]; then
  WRANGLER="/home/ian/Projects/pinboard-reorg/node_modules/.bin/wrangler"
fi

cd "$DIR"

echo "=== Deploying Cloudflare Scheduler (14,44 * * * *) ==="
"$WRANGLER" deploy

echo ""
echo "=== Checking GITHUB_TOKEN secret ==="
echo "If you haven't set GITHUB_TOKEN yet, run:"
echo "  gh auth token | $WRANGLER secret put GITHUB_TOKEN"
echo ""
echo "Deployment complete!"
