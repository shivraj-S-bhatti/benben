# Autonomy roadmap (not in the demo)

**Nothing in this folder ran on the robot.** In the demo a person drives BenBen with the handheld remote, and the Mac only listens. This page is the path from that to a dog that walks the route on its own.

## Step 1, now: human-piloted inspection

A person drives. `capture/record.py` records camera, LiDAR and pose over a listen-only WebRTC link and sends no motor, mode or stand commands. Muse Spark judges the stills afterwards. Every step below keeps this recording and judging loop unchanged and only replaces the person holding the remote.

## Step 2: patrol on a known route with DimOS

DimOS 0.0.15 ships a `unitree-go2` blueprint (`dimos/robot/unitree/go2/blueprints/smart/unitree_go2.py`) that wires four modules together:

| Module | Job |
|---|---|
| `PGOVoxelMapper` | Builds a voxel map from LiDAR with pose-graph loop closure |
| `ReplanningAStarPlanner` | Plans to a goal on the costmap and replans as the map changes |
| `WavefrontFrontierExplorer` | Picks unexplored frontiers to map new ground |
| `PatrollingModule` | `start_patrol` / `stop_patrol`; keeps picking goals from a patrol router |

The plan:

1. Map the estate once with `unitree-go2-map` while a person drives, and save the map.
2. Patrol the walking route, not the whole area. DimOS's patrol routers are `random`, `coverage` and `frontier`; none follows a fixed route. The new piece is a small router that returns the route's checkpoints in order (the doorway steps, the parking-lot stairs, the curb edge).
3. At each checkpoint, stop, record and triage exactly as in step 1.
4. Prove it in DimOS replay and simulation before the real dog, with a spotter holding the remote.

`navigation_skeleton.py` is the gate we would put in front of any planner. It is dry-run only: it holds (zero velocity) on a stale observation, a stale map, a frame mismatch, unverified clearance or a step on the path, and rejects commands above illustrative speed limits. It connects to nothing and sends nothing.

## Step 3: VLA follow-up

A vision-language-action model is a later research track. Our teammate's notes (`experiments/teammate_vla/README.md` in the earlier `video-to-gym-lab` repo) cover an offline SmolVLA probe on a Windows GPU laptop. SmolVLA is a manipulator policy with a six-value arm output, and that output must never be sent to the Go2. Only the offline self-tests and the setup dry-run have passed; the GPU install, weight download and inference have not run. A navigation VLA for the dog would need its own model, data and evaluation.

## Safety facts

- **DimOS live connect stands the dog up.** Starting a DimOS Go2 blueprint against the real robot puts it on its feet; Ctrl-C lies it down. Keep a spotter with the remote and 2 m clear.
- **Nov 3: unexpected motion.** Unexpected physical motion was reported on 2026-11-03, and BenBen rolled over*. Telemetry from before then is not evidence of safe motion.
- **The old `go2_live` adapter is disabled.** Its four scripts that talked to the robot raise an error on import, and none of them is in this repo. `navigation_skeleton.py` came from the same folder; it is a dry-run file and runs standalone.
- **DimOS live did not connect on Nov 4.** It hung for over two minutes and we dropped it. Replay works on the Mac.
