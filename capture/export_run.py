"""Turn a DimOS Go2 recording (.db) into dashboard inputs: a top-down LiDAR map PNG and timestamped camera frames.

    python capture/export_run.py <recording.db> .artifacts/run-export
    python capture/export_run.py go2_short .artifacts/run-export   # DimOS sample

Writes map.png (height-shaded voxels from above, odometry path in teal), frames/NNN.jpg, and manifest.json
(each frame's time and pose). Reads the file only; nothing here talks to a robot.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image as PILImage, ImageDraw

PX_PER_M = 40  # ponytail: fixed scale, fine for rooms and a walkway; make it fit-to-width for big outdoor runs


def top_down(points, path, size_cap=2400):
    lo = np.minimum(points[:, :2].min(0), path.min(0) if len(path) else points[:, :2].min(0)) - 0.5
    hi = np.maximum(points[:, :2].max(0), path.max(0) if len(path) else points[:, :2].max(0)) + 0.5
    scale = min(PX_PER_M, size_cap / max(hi - lo))
    w, h = ((hi - lo) * scale).astype(int) + 1
    to_px = lambda xy: np.stack([(xy[:, 0] - lo[0]) * scale, h - 1 - (xy[:, 1] - lo[1]) * scale], 1).astype(int)
    z = points[:, 2]
    keep = (z > 0.05) & (z < 2.0)  # drop floor and ceiling so obstacles stand out
    img = np.full((h, w, 3), 251, np.uint8)
    floor = to_px(points[~keep, :2])
    img[floor[:, 1], floor[:, 0]] = (228, 228, 222)
    obs, zz = to_px(points[keep, :2]), z[keep]
    order = np.argsort(zz)  # tallest drawn last
    shade = (25 + 110 * (1 - np.clip(zz[order] / 1.0, 0, 1))).astype(np.uint8)
    img[obs[order, 1], obs[order, 0]] = np.stack([shade, shade, shade + 6], 1)
    out = PILImage.fromarray(img)
    if len(path) > 1:
        ImageDraw.Draw(out).line([tuple(p) for p in to_px(path)], fill=(15, 118, 110), width=3)
    return out, {"origin_m": lo.tolist(), "px_per_m": float(scale), "size_px": [int(w), int(h)]}


def main(src, out_dir, n_frames=12):
    # dimos is imported here so record.py can reuse top_down() without installing dimos
    from dimos.mapping.voxels.module import VoxelMapTransformer
    from dimos.memory.store.sqlite import SqliteStore
    from dimos.msgs.sensor_msgs.Image import Image
    from dimos.msgs.sensor_msgs.PointCloud2 import PointCloud2
    from dimos.utils.data import get_data

    out = Path(out_dir)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    path = src if src.endswith(".db") else str(get_data(f"{src}.db"))
    with SqliteStore(path=path) as db:
        print("streams:", db.list_streams())
        lidar = db.stream("lidar", PointCloud2)
        n_lidar = lidar.count()
        world = lidar.transform(VoxelMapTransformer(voxel_size=0.05)).last().data
        odom = np.array([o.pose_tuple[:2] for o in db.stream("odom") if o.pose_tuple]) if "odom" in db.list_streams() else np.zeros((0, 2))
        png, frame = top_down(world.points_f32(), odom)
        png.save(out / "map.png")
        cam = db.stream("color_image", Image)
        total = cam.count()
        picks = set(np.linspace(0, total - 1, min(n_frames, total)).astype(int).tolist())
        frames = []
        for i, obs in enumerate(cam):
            if i not in picks:
                continue
            name = f"frames/{len(frames):03d}.jpg"
            (out / name).write_bytes(obs.data.to_jpeg_bytes(quality=85))
            frames.append({"file": name, "ts": obs.ts, "at": datetime.fromtimestamp(obs.ts, timezone.utc).isoformat(),
                           "pose": list(obs.pose_tuple) if obs.pose_tuple else None})
    (out / "manifest.json").write_text(json.dumps({"source": path, "map": {"file": "map.png", **frame},
                                                   "lidar_frames": n_lidar, "frames": frames}, indent=2))
    print(f"map.png {frame['size_px']} px, {len(frames)} frames -> {out}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
