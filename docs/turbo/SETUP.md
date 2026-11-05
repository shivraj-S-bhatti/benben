# Setup

`setup/bootstrap.sh` installs each piece of BenBen with one command. Pins (package versions, the MapAnything commit and weights revision, Brush release and sha256) live in `setup/models.lock.json`. No subcommand connects to the robot, and none prints the Meta key.

```bash
bash setup/bootstrap.sh check     # installs nothing; exits 1 if python3 3.10+, a CA bundle or uv is missing
bash setup/bootstrap.sh all       # app + capture + twin + splat
bash setup/bootstrap.sh models    # model inventory with licenses and sizes
```

Add `--dry-run` to any subcommand to print its install steps without running them.

| Subcommand | Installs | Lands in | Verifies with |
|---|---|---|---|
| `check` | nothing | | python3, CA certs, uv, ffmpeg, PortAudio, COLMAP, Brush, Meta key, model caches, venvs, GPU backend |
| `app` | nothing (stdlib only) | | `unittest` over `app/test_*.py`, `app/verdict_eval.py --self-test` |
| `capture` | `unitree-webrtc-connect==2.2.0 av==17.1.0 numpy==2.5.4 pillow==13.0.0` | `.venv-capture` | `capture/record.py --self-test` (offline, synthetic frames) |
| `twin` | `torch==2.15.0 torchvision==0.29.2 matplotlib==3.11.2`, MapAnything at commit `3d10cf7a`, weights `facebook/map-anything-apache` rev `00f9c245`, COLMAP | `.venv-twin`, `.artifacts/src/map-anything`, the Hugging Face cache, Homebrew/apt | imports `mapanything`, resolves the weights with `local_files_only=True`, runs a matmul on CUDA/MPS/CPU, prints the COLMAP version |
| `splat` | Brush v0.3.0 release binary for this OS/arch, sha256-checked against the lock | `.artifacts/tools/brush` | `brush_app --version` |
| `dimos` | `dimos[base,unitree]==0.0.15`, plus the SQLite guard below | `.venv-dimos` | `dimos --help`, opens a DimOS SQLite connection in memory |

Every subcommand skips what is already there: an existing venv, a MapAnything checkout at the pinned commit, weights already in the Hugging Face cache, a `colmap` on PATH, a Brush tarball whose sha256 matches. The `uv pip install` steps re-run but only audit the installed packages.

The repo `.gitignore` lists `.venv/` but not `.venv-capture` and the others. Git still ignores them because `uv venv` writes a `.gitignore` containing `*` into each venv.

## What ran on this Mac

Run on 2026-11-04 on a MacBook Pro, Apple M1 Pro, 16 GB, macOS 27.0.1, `/bin/bash` 3.2.57, uv 0.6.14. `python3` is the pyenv shim to the python.org 3.12.8 build. MapAnything weights and COLMAP were already present from the twin run in `video-to-gym-lab/.artifacts/twin/`.

| Run | Result | Wall time |
|---|---|---|
| `check`, before any install | exit 0; Brush and the three venvs missing | 2 s |
| `app` | 14 tests OK, verdict self-test OK | 8 s |
| `capture`, first run | venv created, 44 packages (downloaded opencv-python 46 MB and av 17 MB, built pyaudio), self-test saved 45 video frames, 15 LiDAR clouds, 2 stills and a map | 19 s |
| `capture`, second run | venv skipped, 4 packages audited, self-test OK | 2 s |
| `twin --dry-run` | printed every step; weights and COLMAP reported as skipped | 2 s |
| `twin`, first run | torch came from the local uv cache, MapAnything checkout fetched from GitHub, weights download skipped, COLMAP skipped; verify: `torch 2.15.0 on mps` | 19 s |
| `twin`, second run | everything skipped, verify OK | 7 s |
| `splat`, first run | 39.5 MiB download, `sha256 OK`, `brush-cli 0.3.0` | 11 s |
| `splat`, second run | skipped, tarball sha256 matches | 1 s |
| `splat` with a wrong sha256 in a copy of the lock | `sha256 MISMATCH`, download deleted, exit 1 | |
| `check` with `PATH=/usr/bin:/bin` | system python3 3.9.6 and no uv: exit 1 | |
| `all`, everything present | all four skip paths, all verifies OK | 17 s |
| `dimos --dry-run` | printed the warning and both install steps | 0 s |
| `dimos` | not run here (large download; not needed for the loop) | |
| Any Linux/WSL path | not run here | |

`check` after `all`:

```text
== BenBen environment (Darwin arm64)
  ok       python3                3.12.8 at /Users/apple/.pyenv/shims/python3
  ok       CA certs               python3 has none; scripts set SSL_CERT_FILE=/etc/ssl/cert.pem
  ok       uv                     uv 0.6.14 (a4cec56dc 2025-04-09)
  ok       ffmpeg                 ffmpeg version 9.0.2
  ok       PortAudio              /opt/homebrew/include/portaudio.h
  ok       colmap                 COLMAP 4.2.1
  ok       Brush                  brush-cli 0.3.0
  ok       Meta key               Keychain item meta-model-api exists (value not shown)
  ok       MapAnything weights    rev 00f9c245, 4.6G
  ok       torch hub DINOv2       /Users/apple/.cache/torch/hub
  ok       .venv-capture          Python 3.12.8
  ok       .venv-twin             Python 3.12.8
  missing  .venv-dimos            bootstrap.sh dimos
  ok       GPU backend            MPS (torch 2.15.0)
check: all required pieces present
done: check in 4s
```

(`du` reports the 4,914,062,480-byte weights file as 4.6G, in GiB.)

`twin` checks the install, not reconstruction. MapAnything inference was not rerun here; the twin README records 121.6 s for 32 views on this Mac and a 60-view run that swapped and was killed.

On a fresh Mac the slow steps are the ones this run skipped. The twin run measured `brew install colmap` at 4 min 53 s, torch plus the MapAnything install at 1 min 38 s and the 4.9 GB weights download plus model load at 863 s.

## Things that bite

- **CA certificates.** python.org and pyenv builds on macOS ship without a CA bundle, and HTTPS calls fail with `CERTIFICATE_VERIFY_FAILED`. `check` reports which case you are in. `bootstrap.sh` and `run_app.sh` both set `SSL_CERT_FILE=/etc/ssl/cert.pem` when Python has no bundle of its own.
- **Meta key.** `check` only tests that the Keychain item `meta-model-api` (or `.artifacts/benben-secrets/meta-api-key`) exists. To store the key, run `bash setup/run_app.sh --smoke`: it asks at a hidden Keychain prompt, so the key never reaches argv, shell history or Git.
- **PortAudio.** `unitree_webrtc_connect` and DimOS pull in `pyaudio`, which compiles against PortAudio headers. `capture` and `dimos` stop early without them: `brew install portaudio`, or `sudo apt-get install -y portaudio19-dev`.
- **Which Python the venvs get.** `uv venv --python 3.12` picked python.org 3.12.8 here. The Homebrew 3.12 would work too.

## DimOS (optional)

**Live DimOS stands the dog up when it connects, and earlier tests saw unexpected motion.** `bootstrap.sh dimos` installs software only and never connects. Recording uses `capture/record.py`, which is listen-only. Run a live blueprint only as its own hardware session, with a spotter and the physical remote in hand.

DimOS 0.0.15 calls `conn.enable_load_extension(True)` unguarded in `dimos/memory/utils/sqlite.py`. python.org macOS builds compile `sqlite3` without that method, so opening a DimOS SQLite store fails. When the venv's Python lacks it, `bootstrap.sh dimos` wraps those three lines in `if hasattr(conn, "enable_load_extension"):`, the same patch running in `video-to-gym-lab/.artifacts/dimos/.venv`. Only vector search needs `sqlite-vec`. The patch was checked against the upstream 0.0.15 file: the result differs from the working venv only in the comment text. Homebrew and uv-managed Pythons on this Mac have the method and need no patch.

## Linux and WSL

The same script runs on Linux x86_64. None of this was run here.

- `twin` installs torch with `uv pip install --torch-backend auto`, which picks the CUDA wheel for the installed driver, and gets COLMAP from `sudo apt-get install -y colmap`. Ubuntu's packaged COLMAP is older than 4.2.1*.
- `splat` downloads `brush-app-x86_64-unknown-linux-gnu.tar.xz` (sha256 `4f0f9a87…` in the lock). Other OS/arch pairs exit with a message.
- **gsplat** (Apache-2.0, nerfstudio) is the alternative splat trainer on a CUDA GPU. `bootstrap.sh` does not install it. Install it into a CUDA torch venv with `pip install gsplat`; it compiles its CUDA kernels on first use and needs a CUDA toolkit matching torch*.
- **VGGT** runs on CUDA only. The working recipe is `video-to-gym-lab/setup/aditya/install.sh vision`: torch 2.8.0 / torchvision 0.23.0 from the cu128 index (RTX 50xx needs CUDA 12.8), then VGGT's own requirements without its torch pins. `bootstrap.sh` does not install it.

## Models

`bash setup/bootstrap.sh models` prints this from the lock. Sizes and licenses for Hugging Face models come from the Hugging Face API on 2026-11-04 (largest file, one weights format).

| Model | ID | Where it runs | License | Size | Installed by |
|---|---|---|---|---|---|
| Muse Spark | `muse-spark-1.3` | Meta API | Meta API terms* | none | nothing to install |
| SAM 3.1 | `sam-3.1` | Meta API | Meta API terms* | none | nothing to install |
| Voice Transcribe | `muse-voice-transcribe-1.0` | Meta API | Meta API terms* | none | nothing to install |
| MapAnything | `facebook/map-anything-apache` @ `00f9c245` | local, MPS or CUDA | Apache-2.0 | 4.91 GB | `twin` |
| VGGT-1B | `facebook/VGGT-1B` @ `860abec7` | local, CUDA, optional | CC-BY-NC-4.0 (non-commercial) | 5.03 GB | not installed |
| SAM 2.1 Hiera-L | `facebook/sam2.1-hiera-large` @ `665f8e2a` | local, optional, ungated | Apache-2.0 | 0.90 GB | not installed |
| SAM 3 | `facebook/sam3` @ `3c879f39` | local, optional, gated (manual approval) | SAM License* (HF tag `other`) | 3.44 GB | not installed |
| Brush | v0.3.0 release | local binary, Metal/WebGPU | Apache-2.0 | 41.4 MB macOS, 44.2 MB Linux | `splat` |

MapAnything also fetches DINOv2 hub code (about 4 MB) into `~/.cache/torch/hub` on its first model load; `twin` does not pre-fetch it.
