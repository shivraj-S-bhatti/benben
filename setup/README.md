# Mac setup

## Dashboard

Python 3.10+ from the standard library is enough. `run_app.sh` loads the Meta API key and starts `app/server.py`:

```bash
bash setup/run_app.sh                       # Meta API, key in Keychain item "meta-model-api"
bash setup/run_app.sh --smoke               # one tiny text-only call to check the key
META_PROVIDER=baseten bash setup/run_app.sh # Muse Spark Open on Baseten (untested fallback)
```

The first run asks for the key at a hidden Keychain prompt, so it never lands in a command argument, the shell history or the repo. The script also sets `SSL_CERT_FILE=/etc/ssl/cert.pem`, because python.org and pyenv builds on macOS ship without CA certificates and fail HTTPS calls to Meta.

## Recording from BenBen

The recorder needs four packages. We ran it in the virtualenv that DimOS 0.0.15 installs, which includes them; this minimal set is what the scripts import:

```bash
python3.12 -m venv .artifacts/venv
.artifacts/venv/bin/pip install unitree_webrtc_connect av numpy pillow
```

1. Turn BenBen on and join its Wi-Fi hotspot from the Mac.
2. Start the recorder, then drive with the handheld remote. Ctrl-C stops early and still saves.

   ```bash
   .artifacts/venv/bin/python capture/record.py --seconds 240
   ```

   It connects listen-only and sends no motor, mode or stand commands. Each run lands in `.artifacts/benben-runs/<UTC time>/`: `video.mp4`, every LiDAR cloud, every pose, 1 fps stills with `manifest.json`, and a top-down `map.png`.
3. Render the camera/LiDAR split screen and ask Muse to triage chosen stills:

   ```bash
   .artifacts/venv/bin/python capture/render_lidar.py .artifacts/benben-runs/<run>
   export MODEL_API_KEY="$(security find-generic-password -a "$USER" -s meta-model-api -w)"
   SSL_CERT_FILE=/etc/ssl/cert.pem python3 capture/beat_verdicts.py .artifacts/benben-runs/<run> 10 48 144 160
   ```

   `beat_verdicts.py` writes `verdicts.json` with each frame's capture time, model, latency and Muse's answer.
4. Load the stills into the dashboard with `app/import_capture.py` (see the top-level README).

Offline check, no robot: `.artifacts/venv/bin/python capture/record.py --self-test`.

`capture/export_run.py` converts a DimOS `.db` recording into the same `frames/`, `manifest.json` and `map.png` shape. It is the only capture script that needs `pip install dimos==0.0.15`.
