#!/usr/bin/env bash
# BenBen one-command setup. Installs software only: nothing here connects to the robot,
# and no secret is ever printed or passed in argv. Pins live in setup/models.lock.json.
#   bash setup/bootstrap.sh check      # report only, installs nothing; nonzero if a required piece is missing
#   bash setup/bootstrap.sh app        # stdlib dashboard: run its tests
#   bash setup/bootstrap.sh capture    # .venv-capture + recorder self-test (no robot)
#   bash setup/bootstrap.sh twin       # .venv-twin with MapAnything, pinned weights, COLMAP
#   bash setup/bootstrap.sh splat      # Brush release binary, sha256-checked
#   bash setup/bootstrap.sh dimos      # optional DimOS 0.0.15 in .venv-dimos (never run live from here)
#   bash setup/bootstrap.sh models     # model inventory
#   bash setup/bootstrap.sh all        # app capture twin splat
# Add --dry-run to any subcommand to print the install steps without running them.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOCK="$ROOT/setup/models.lock.json"
OS="$(uname -s)"; ARCH="$(uname -m)"
DRY=0; CMD=""
for a in "$@"; do case "$a" in --dry-run) DRY=1 ;; *) CMD="$a" ;; esac; done
HF_HUB="${HF_HOME:-$HOME/.cache/huggingface}/hub"
TORCH_HUB="${TORCH_HOME:-$HOME/.cache/torch}/hub"
BRUSH_DIR="$ROOT/.artifacts/tools/brush"
MA_SRC="$ROOT/.artifacts/src/map-anything"

say()  { printf '\n== %s\n' "$*"; }
run()  { echo "+ $*"; if [[ $DRY == 0 ]]; then "$@"; fi; }
lock() { python3 -c 'import json,sys,functools
v=functools.reduce(lambda d,k:d[int(k)] if isinstance(d,list) else d[k],sys.argv[2].split("."),json.load(open(sys.argv[1])))
print(" ".join(v) if isinstance(v,list) else v)' "$LOCK" "$1"; }
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }
need_uv() { command -v uv >/dev/null || { echo "uv is missing. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }; }
portaudio_h() { ls /opt/homebrew/include/portaudio.h /usr/local/include/portaudio.h /usr/include/portaudio.h 2>/dev/null | head -1; }
need_portaudio() {  # pyaudio, pulled in by unitree_webrtc_connect and dimos, compiles against it
  [[ -n "$(portaudio_h)" ]] || { echo "PortAudio headers missing: brew install portaudio  (Linux: sudo apt-get install -y portaudio19-dev)"; exit 1; }
}
mkvenv() {  # $1 = venv dir; uv writes a '*' .gitignore inside it, so Git ignores the venv
  if [[ -x "$1/bin/python" ]]; then echo "skip: $1 exists ($("$1/bin/python" --version))"
  else run uv venv --python "$(lock python)" "$1"; fi
}
# python.org/pyenv builds on macOS ship without CA certs (CERTIFICATE_VERIFY_FAILED); same fix as run_app.sh.
certs_ok() { env -u SSL_CERT_FILE python3 -c 'import ssl,os,sys;p=ssl.get_default_verify_paths();sys.exit(not any(x and os.path.exists(x) for x in (p.cafile,p.openssl_cafile)))'; }
[[ -z "${SSL_CERT_FILE:-}" && -f /etc/ssl/cert.pem ]] && ! certs_ok && export SSL_CERT_FILE=/etc/ssl/cert.pem
MA_REV="$(lock models.3.revision)"
MA_SNAP="$HF_HUB/models--facebook--map-anything-apache/snapshots/$MA_REV"
brush_asset() { lock "brush.assets.$OS-$ARCH.file" 2>/dev/null || true; }
brush_bin() { local f; f="$(brush_asset)"; echo "$BRUSH_DIR/${f%.tar.xz}/brush_app"; }

check() {
  local miss=0 py
  ok()  { printf '  ok       %-22s %s\n' "$1" "$2"; }
  opt() { printf '  missing  %-22s %s\n' "$1" "$2"; }
  bad() { printf '  MISSING  %-22s %s  (required)\n' "$1" "$2"; miss=1; }
  say "BenBen environment ($OS $ARCH)"
  if py="$(python3 -c 'import sys;print("%d.%d.%d"%sys.version_info[:3]);sys.exit(sys.version_info<(3,10))' 2>/dev/null)"
  then ok python3 "$py at $(command -v python3)"; else bad python3 "need 3.10+ (found ${py:-none})"; fi
  if certs_ok 2>/dev/null; then ok "CA certs" "python3's own bundle"
  elif [[ -f /etc/ssl/cert.pem ]]; then ok "CA certs" "python3 has none; scripts set SSL_CERT_FILE=/etc/ssl/cert.pem"
  else bad "CA certs" "python3 has no CA bundle and /etc/ssl/cert.pem is absent"; fi
  if command -v uv >/dev/null; then ok uv "$(uv --version)"; else bad uv "curl -LsSf https://astral.sh/uv/install.sh | sh"; fi
  if command -v ffmpeg >/dev/null; then ok ffmpeg "$(ffmpeg -version | head -1 | cut -d' ' -f1-3)"; else opt ffmpeg "brew/apt install ffmpeg (frame extraction)"; fi
  if [[ -n "$(portaudio_h)" ]]; then ok PortAudio "$(portaudio_h)"; else opt PortAudio "brew install portaudio / apt portaudio19-dev (capture, dimos)"; fi
  if command -v colmap >/dev/null; then ok colmap "$(colmap -h 2>&1 | head -1 | cut -d' ' -f1-2)"; else opt colmap "bootstrap.sh twin"; fi
  if [[ -x "$(brush_bin)" ]]; then ok Brush "$("$(brush_bin)" --version 2>&1 | head -1)"; else opt Brush "bootstrap.sh splat"; fi
  if [[ -s .artifacts/benben-secrets/meta-api-key ]]; then ok "Meta key" "file in .artifacts/benben-secrets (value not shown)"
  elif [[ $OS == Darwin ]] && security find-generic-password -a "$USER" -s meta-model-api >/dev/null 2>&1
  then ok "Meta key" "Keychain item meta-model-api exists (value not shown)"
  else opt "Meta key" "bash setup/run_app.sh --smoke asks at a hidden prompt"; fi
  if [[ -s "$MA_SNAP/model.safetensors" ]]; then ok "MapAnything weights" "rev ${MA_REV:0:8}, $(du -shL "$MA_SNAP/model.safetensors" | cut -f1)"
  else opt "MapAnything weights" "bootstrap.sh twin (4.9 GB)"; fi
  if [[ -d "$TORCH_HUB/facebookresearch_dinov2_main" ]]; then ok "torch hub DINOv2" "$TORCH_HUB"
  else opt "torch hub DINOv2" "fetched (about 4 MB) on first MapAnything load"; fi
  for v in .venv-capture .venv-twin .venv-dimos; do
    if [[ -x "$v/bin/python" ]]; then ok "$v" "$("$v/bin/python" --version)"; else opt "$v" "bootstrap.sh ${v#.venv-}"; fi
  done
  if [[ -x .venv-twin/bin/python ]]; then
    ok "GPU backend" "$(.venv-twin/bin/python -c 'import torch;print("CUDA" if torch.cuda.is_available() else "MPS" if torch.backends.mps.is_available() else "CPU", "(torch", torch.__version__ + ")")')"
  elif command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; then ok "GPU backend" "CUDA (nvidia-smi; torch not installed yet)"
  elif [[ $OS-$ARCH == Darwin-arm64 ]]; then ok "GPU backend" "MPS expected (Apple Silicon; torch not installed yet)"
  else ok "GPU backend" "CPU only"; fi
  [[ $miss == 0 ]] && echo "check: all required pieces present" || echo "check: required pieces missing"
  return $miss
}

app() {
  say "App: stdlib only, needs python3 3.10+; runs its tests"
  python3 -c 'import sys;sys.exit(sys.version_info<(3,10))' || { echo "python3 is older than 3.10"; exit 1; }
  run python3 -m unittest discover -s app -p 'test_*.py'
  run python3 app/verdict_eval.py --self-test
  echo "app: OK. Start it with: bash setup/run_app.sh  (Meta key at a hidden Keychain prompt)"
}

capture() {
  say "Capture: .venv-capture with $(lock capture.packages); then record.py --self-test (offline, no robot)"
  need_uv; need_portaudio; mkvenv .venv-capture
  # shellcheck disable=SC2046
  run uv pip install --python .venv-capture/bin/python $(lock capture.packages)
  run .venv-capture/bin/python capture/record.py --self-test
}

twin() {
  local commit pkgs; commit="$(lock twin.mapanything_commit)"; pkgs="$(lock twin.packages)"
  say "Twin: .venv-twin with $pkgs, MapAnything @ ${commit:0:8}, weights rev ${MA_REV:0:8}, COLMAP"
  need_uv; mkvenv .venv-twin
  # shellcheck disable=SC2086
  if [[ $OS == Linux ]]; then run uv pip install --python .venv-twin/bin/python --torch-backend auto $pkgs
  else run uv pip install --python .venv-twin/bin/python $pkgs; fi
  if [[ "$(git -C "$MA_SRC" rev-parse HEAD 2>/dev/null)" == "$commit" ]]; then echo "skip: $MA_SRC at ${commit:0:8}"
  else
    run mkdir -p "$MA_SRC"; run git -C "$MA_SRC" init -q
    git -C "$MA_SRC" remote get-url origin >/dev/null 2>&1 || run git -C "$MA_SRC" remote add origin "$(lock twin.mapanything_repo)"
    run git -C "$MA_SRC" fetch -q --depth 1 origin "$commit"; run git -C "$MA_SRC" checkout -q FETCH_HEAD
  fi
  run uv pip install --python .venv-twin/bin/python -e "$MA_SRC"
  if [[ -s "$MA_SNAP/model.safetensors" ]]; then echo "skip: MapAnything weights cached at $MA_SNAP"
  else run .venv-twin/bin/python -c 'import sys;from huggingface_hub import snapshot_download as d;print(d(sys.argv[1],revision=sys.argv[2]))' \
         facebook/map-anything-apache "$MA_REV"; fi
  if command -v colmap >/dev/null; then echo "skip: colmap present ($(colmap -h 2>&1 | head -1 | cut -d' ' -f1-2))"
  elif [[ $OS == Darwin ]]; then run brew install colmap
  else run sudo apt-get install -y colmap; fi
  [[ $DRY == 1 ]] && { echo "twin: dry run, nothing installed or verified"; return; }
  say "Verify twin"
  .venv-twin/bin/python - "$MA_REV" <<'EOF'
import sys, torch, mapanything
from huggingface_hub import snapshot_download
path = snapshot_download("facebook/map-anything-apache", revision=sys.argv[1], local_files_only=True)
dev = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
x = torch.ones(256, 256, device=dev); assert (x @ x).sum().item() == 256 ** 3
print(f"twin: OK. torch {torch.__version__} on {dev}; weights {path}")
EOF
  colmap -h 2>&1 | head -1
}

splat() {
  local f sha tmp; f="$(brush_asset)"
  [[ -n $f ]] || { echo "No Brush $(lock brush.version) binary for $OS-$ARCH. Linux+CUDA alternative: gsplat (see docs/turbo/SETUP.md)."; exit 1; }
  sha="$(lock "brush.assets.$OS-$ARCH.sha256")"
  say "Splat: Brush $(lock brush.version) ($f) into $BRUSH_DIR, sha256 ${sha:0:12}..."
  if [[ -x "$(brush_bin)" && -f "$BRUSH_DIR/$f" && "$(sha256 "$BRUSH_DIR/$f")" == "$sha" ]]; then echo "skip: Brush present and tarball sha256 matches"
  else
    run mkdir -p "$BRUSH_DIR"
    if [[ -f "$BRUSH_DIR/$f" && "$(sha256 "$BRUSH_DIR/$f")" == "$sha" ]]; then echo "skip: tarball cached, sha256 matches"
    else
      tmp="$BRUSH_DIR/$f.part"; echo "+ curl -fsSL -o $tmp $(lock brush.url)$f  (then sha256 check)"
      if [[ $DRY == 0 ]]; then
        curl -fsSL --retry 2 -o "$tmp" "$(lock brush.url)$f"
        [[ "$(sha256 "$tmp")" == "$sha" ]] || { rm -f "$tmp"; echo "sha256 MISMATCH for $f; deleted the download"; exit 1; }
        mv "$tmp" "$BRUSH_DIR/$f"; echo "sha256 OK"
      fi
    fi
    run tar xf "$BRUSH_DIR/$f" -C "$BRUSH_DIR"
  fi
  [[ $OS == Linux ]] && echo "note: on Linux+CUDA, gsplat (Apache-2.0) is the alternative trainer; not installed here."
  [[ $DRY == 1 ]] && { echo "splat: dry run, nothing installed or verified"; return; }
  echo "splat: OK. $("$(brush_bin)" --version 2>&1 | head -1) at $(brush_bin)"
}

dimos() {
  cat <<'EOF'

!!! DimOS: install only. A live DimOS blueprint STANDS THE DOG UP on connect, and earlier
!!! tests saw unexpected motion. This script never connects. Run live only as a separate,
!!! spotted hardware session with the physical remote in hand. Use capture/record.py instead.
EOF
  local py=.venv-dimos/bin/python
  say "DimOS: .venv-dimos with $(lock dimos.package)"
  need_uv; need_portaudio; mkvenv .venv-dimos
  run uv pip install --python "$py" --torch-backend "$([[ $OS == Darwin ]] && echo cpu || echo auto)" "$(lock dimos.package)"
  [[ $DRY == 1 ]] && { echo "dimos: dry run, nothing installed or verified"; return; }
  # python.org macOS builds compile sqlite3 without enable_load_extension; DimOS 0.0.15 calls it unguarded.
  "$py" - <<'EOF'
import sqlite3, pathlib, dimos.memory.utils.sqlite as m
if not hasattr(sqlite3.Connection, "enable_load_extension"):
    p = pathlib.Path(m.__file__); s = p.read_text()
    old = "    conn.enable_load_extension(True)\n    sqlite_vec.load(conn)\n    conn.enable_load_extension(False)\n"
    if old in s:
        new = '    if hasattr(conn, "enable_load_extension"):  # python.org macOS builds lack it\n' + "".join("    " + l + "\n" for l in old.splitlines())
        p.write_text(s.replace(old, new)); print("patched SQLite extension guard:", p)
    else: print("SQLite extension guard already present")
EOF
  "$py" -c 'import dimos.memory.utils.sqlite as m; m.open_sqlite_connection(":memory:").close()'
  .venv-dimos/bin/dimos --help >/dev/null && echo "dimos: OK (CLI loads, SQLite opens). No robot connected."
}

models() {
  python3 - "$LOCK" <<'EOF'
import json, sys
for m in json.load(open(sys.argv[1]))["models"]:
    print(f"{m['name']:<30} {m['id']:<30} {m['kind']}")
    print(f"{'':<30} license {m['license']}; size {m['size']}; install: {m['install']}" + (f"; rev {m['revision'][:12]}" if "revision" in m else ""))
print("* = unverified; check before relying on it.")
EOF
}

all() { app; capture; twin; splat; }
case "$CMD" in
  check|app|capture|twin|splat|dimos|models|all) "$CMD"; echo "done: $CMD in ${SECONDS}s" ;;
  *) sed -n 2,13p "$0"; exit 2 ;;
esac
