#!/usr/bin/env bash
# Your studio with a private online link (for your phone and your Netlify site). Needs cloudflared once.
exec "$(dirname "$0")/start.sh" online
