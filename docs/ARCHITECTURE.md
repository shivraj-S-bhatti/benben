# Architecture

```mermaid
flowchart LR
    remote([Person with handheld remote]) -->|drives| go2[Unitree Go2<br/>BenBen]
    go2 -->|listen-only WebRTC| rec["capture/record.py<br/>video · LiDAR · pose"]
    rec -->|stills + manifest.json| muse["Muse Spark muse-spark-1.3<br/>reroute · flag · report · human"]
    rec -->|stills| sam["SAM 3.1<br/>obstacle box"]
    rec -->|LiDAR + pose| lidar["capture/render_lidar.py<br/>camera/LiDAR split"]
    rec -->|import_capture.py| store[("Evidence store<br/>run folder + SQLite, timestamped")]
    muse -->|verdicts.json| store
    sam -->|boxes| store
    lidar -->|lidar_split.mp4| store
    store --> dash["Dashboard<br/>app/server.py + static/"]
    planner["DimOS mapper, planner, patrol<br/>(roadmap)"] -.->|motion, not in demo| go2
    store -.->|route checkpoints| planner
```

| Stage | File | Notes |
|---|---|---|
| Record | `capture/record.py` | Subscribes to camera, LiDAR and pose. Sends no motor, mode or stand commands. Writes one folder per run. |
| Judge | `capture/beat_verdicts.py`, `app/copilot.py` | One Muse Spark call per still, strict JSON schema, one action per frame. SAM 3.1 boxes go through `/api/segment`. |
| Keep evidence | `app/import_capture.py`, `app/server.py` | The run folder keeps the raw recording and Muse's `verdicts.json`. Each imported still becomes a dashboard observation with its recorder timestamp and SHA-256. Issues are separate records; only a person resolves one. |
| Show | `app/static/` | Localhost only. Model answers must cite photos that were actually sent, or the server rejects them. |
| Act (roadmap) | `autonomy/` | Dashed in the diagram. See [autonomy/README.md](../autonomy/README.md). |

All recordings, workspaces and keys live under the ignored `.artifacts/` folder.
