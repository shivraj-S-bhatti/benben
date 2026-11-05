#!/usr/bin/env bash
# Start the BenBen dashboard with the Meta key loaded from local secret storage.
# First run asks for the key at a hidden prompt; it never touches argv, history or Git.
#   bash setup/run_app.sh                         # Meta API (MODEL_API_KEY)
#   META_PROVIDER=baseten bash setup/run_app.sh   # open-weights fallback (BASETEN_API_KEY)
#   bash setup/run_app.sh --data-dir .artifacts/demo-workspace   # extra args go to server.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ "${META_PROVIDER:-meta}" == baseten ]]; then VAR=BASETEN_API_KEY; KC=baseten-api; FILE=baseten-api-key
else VAR=MODEL_API_KEY; KC=meta-model-api; FILE=meta-api-key; fi
DIR="$ROOT/.artifacts/benben-secrets"   # ignored by Git; same place as the earlier key helper

load_key() {
  if [[ -s "$DIR/$FILE" ]]; then cat "$DIR/$FILE"; return; fi
  if [[ "$(uname -s)" == Darwin ]]; then
    security find-generic-password -a "$USER" -s "$KC" -w 2>/dev/null && return
    echo "Paste the $VAR at the hidden Keychain prompt (twice)." >&2
    security add-generic-password -a "$USER" -s "$KC" -w >&2
    security find-generic-password -a "$USER" -s "$KC" -w
  else
    mkdir -p "$DIR"; chmod 700 "$DIR"
    read -rsp "Paste the $VAR (hidden), then Enter: " key; echo >&2
    [[ -n "$key" ]] || { echo "No key entered." >&2; exit 1; }
    (umask 077; printf '%s' "$key" > "$DIR/$FILE")
    cat "$DIR/$FILE"
  fi
}

# python.org/pyenv builds on macOS ship without CA certs (CERTIFICATE_VERIFY_FAILED); use the system bundle.
[[ -z "${SSL_CERT_FILE:-}" && -f /etc/ssl/cert.pem ]] && export SSL_CERT_FILE=/etc/ssl/cert.pem
export "$VAR=$(load_key)"
[[ -n "${!VAR}" ]] || { echo "No $VAR stored." >&2; exit 1; }
if [[ "${1:-}" == --smoke ]]; then exec python3 app/copilot.py; fi
echo "Open http://127.0.0.1:8766  (add ?walkthrough for the scripted demo)"
exec python3 app/server.py "$@"
