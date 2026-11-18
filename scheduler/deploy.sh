#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRANGLER="/home/ian/Projects/pinboard-reorg/node_modules/.bin/wrangler"

if [ ! -x "$WRANGLER" ]; then
  WRANGLER="npx wrangler"
fi

cd "$DIR"

echo "=== Deploying Cloudflare Hourly Scheduler ==="
"$WRANGLER" deploy

echo ""
echo "=== Checking GITHUB_TOKEN secret ==="
echo "If you haven't set GITHUB_TOKEN yet, run:"
echo "  gh auth token | $WRANGLER secret put GITHUB_TOKEN"
echo ""
echo "Deployment complete!"
