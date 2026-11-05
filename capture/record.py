"""Listen-only BenBen recorder: continuous video, every LiDAR cloud and every pose, while a person drives with the remote.

    python capture/record.py --seconds 300
    python capture/record.py --self-test     # offline, no robot

Sends no motor, mode or stand commands. Each run gets its own folder (.artifacts/benben-runs/<UTC time>/ unless --out):
  video.mp4            every camera frame (fragmented MP4, so a crash still leaves a playable file)
  video_frames.jsonl   one line per frame: index, receive time, stream pts
  lidar/NNNNNN.npy     every LiDAR cloud (float32 xyz, the robot's world frame); lidar.jsonl has times
  poses.jsonl          every robot_pose message: receive time, sensor stamp, position, orientation
  frames/NNN.jpg       1 fps stills + manifest.json + map.png (same shape as export_run.py)
JSONL lines are flushed as they're written. Ctrl-C stops early and still saves.
"""
import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from export_run import top_down  # sibling file; Python puts the script dir on sys.path

VOXEL = 0.05


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


class Run:
    def __init__(self, out):
        self.out = out
        (out / "frames").mkdir(parents=True, exist_ok=True)
        (out / "lidar").mkdir(exist_ok=True)
        self.poses = open(out / "poses.jsonl", "a", buffering=1)
        self.lidar_log = open(out / "lidar.jsonl", "a", buffering=1)
        self.video_log = open(out / "video_frames.jsonl", "a", buffering=1)
        self.container = self.stream = None
        self.t0 = None
        self.last_pts = -1
        self.n_video = self.n_lidar = 0
        self.voxels, self.path, self.stills = set(), [], []
        self.pose = None
        self.last_still = 0.0

    def on_lidar(self, msg, now=None):
        now = now or time.time()
        pts = np.asarray(msg["data"]["data"]["points"], dtype=np.float32).reshape(-1, 3)
        np.save(self.out / "lidar" / f"{self.n_lidar:06d}.npy", pts)
        self.lidar_log.write(json.dumps({"i": self.n_lidar, "ts": now, "stamp": msg["data"].get("stamp"), "points": len(pts)}) + "\n")
        self.n_lidar += 1
        if len(pts):
            self.voxels.update(map(tuple, np.round(pts / VOXEL).astype(np.int32).tolist()))

    def on_odom(self, msg, now=None):
        now = now or time.time()
        d = msg["data"]
        p, q = d["pose"]["position"], d["pose"]["orientation"]
        self.pose = [p["x"], p["y"], p["z"], q["x"], q["y"], q["z"], q["w"]]
        self.poses.write(json.dumps({"ts": now, "stamp": d.get("header", {}).get("stamp"), "pose": self.pose}) + "\n")
        if not self.path or np.hypot(p["x"] - self.path[-1][0], p["y"] - self.path[-1][1]) > 0.05:
            self.path.append((p["x"], p["y"]))

    def on_frame(self, frame, now=None):
        now = now or time.time()
        if self.container is None:
            self.t0 = now
            self.container = av.open(str(self.out / "video.mp4"), "w", options={"movflags": "frag_keyframe+empty_moov"})
            for codec in ("h264_videotoolbox", "libx264", "mpeg4"):
                try:
                    self.stream = self.container.add_stream(codec, rate=30)
                    break
                except Exception:
                    continue
            self.stream.width, self.stream.height, self.stream.pix_fmt = frame.width, frame.height, "yuv420p"
            self.stream.codec_context.time_base = Fraction(1, 1000)
        out = frame.reformat(format="yuv420p")
        # two frames can land in the same ms; the muxer rejects repeated pts (EINVAL)
        out.pts, out.time_base = max(int((now - self.t0) * 1000), self.last_pts + 1), Fraction(1, 1000)
        self.last_pts = out.pts
        try:
            for packet in self.stream.encode(out):
                self.container.mux(packet)
        except av.error.FFmpegError as e:  # never let one bad frame stop stills, LiDAR or pose
            print("video frame skipped:", e, flush=True)
        self.video_log.write(json.dumps({"i": self.n_video, "ts": now, "pts_ms": out.pts, "src_pts": frame.pts}) + "\n")
        self.n_video += 1
        if now - self.last_still >= 1:
            self.last_still = now
            name = f"frames/{len(self.stills):03d}.jpg"
            frame.to_image().save(self.out / name, quality=85)
            self.stills.append({"file": name, "ts": now, "at": iso(now), "pose": self.pose})

    def close(self):
        if self.container is not None:
            for packet in self.stream.encode():
                self.container.mux(packet)
            self.container.close()
        for f in (self.poses, self.lidar_log, self.video_log):
            f.close()
        meta = None
        if self.voxels:
            png, meta = top_down(np.array(list(self.voxels), np.float32) * VOXEL, np.array(self.path, np.float32).reshape(-1, 2))
            png.save(self.out / "map.png")
        (self.out / "manifest.json").write_text(json.dumps({
            "source": "BenBen live (listen-only)", "map": meta and {"file": "map.png", **meta},
            "video": {"file": "video.mp4", "frames": self.n_video}, "lidar_msgs": self.n_lidar, "voxels": len(self.voxels),
            "poses": "poses.jsonl", "frames": self.stills}, indent=2))
        print(f"saved {self.out}: {self.n_video} video frames, {self.n_lidar} lidar clouds, {len(self.stills)} stills, map={'yes' if meta else 'no'}", flush=True)


async def record(seconds, out):
    from unitree_webrtc_connect import UnitreeWebRTCConnection, WebRTCConnectionMethod
    from unitree_webrtc_connect.constants import RTC_TOPIC

    run = Run(out)

    async def on_video(track):
        while True:
            run.on_frame(await track.recv())

    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalAP)
    try:
        await asyncio.wait_for(conn.connect(), 35)
        print(f"connected; recording to {out}. Drive with the remote. Ctrl-C to stop.", flush=True)
        await conn.datachannel.disableTrafficSaving(True)
        conn.datachannel.set_decoder(decoder_type="native")
        conn.datachannel.pub_sub.publish_without_callback(RTC_TOPIC["ULIDAR_SWITCH"], "on")
        conn.datachannel.pub_sub.subscribe(RTC_TOPIC["ULIDAR_ARRAY"], run.on_lidar)
        conn.datachannel.pub_sub.subscribe(RTC_TOPIC["ROBOTODOM"], run.on_odom)
        conn.video.add_track_callback(on_video)
        conn.video.switchVideoChannel(True)
        t0 = time.monotonic()
        while time.monotonic() - t0 < seconds:
            await asyncio.sleep(5)
            print(f"{time.monotonic() - t0:4.0f}s  video {run.n_video}  lidar {run.n_lidar}  voxels {len(run.voxels)}  path pts {len(run.path)}", flush=True)
    finally:
        await conn.disconnect()
        run.close()


def self_test(out):
    run = Run(out)
    t = 1_800_000_000.0
    for i in range(45):  # 1.5 s at 30 fps
        img = np.full((72, 128, 3), i * 5 % 255, np.uint8)
        run.on_frame(av.VideoFrame.from_ndarray(img, format="rgb24"), now=t + i / 30)
        run.on_odom({"data": {"header": {"stamp": {"sec": 1}}, "pose": {"position": {"x": i * 0.02, "y": 0, "z": 0.3},
                                                                       "orientation": {"x": 0, "y": 0, "z": 0, "w": 1}}}}, now=t + i / 30)
        if i % 3 == 0:
            run.on_lidar({"data": {"stamp": t, "data": {"points": np.random.rand(200, 3).tolist()}}}, now=t + i / 30)
    run.close()
    m = json.loads((out / "manifest.json").read_text())
    with av.open(str(out / "video.mp4")) as c:
        decoded = sum(1 for _ in c.decode(video=0))
    assert decoded == 45 and m["video"]["frames"] == 45, decoded
    assert len(list((out / "lidar").glob("*.npy"))) == 15 == m["lidar_msgs"]
    assert sum(1 for _ in open(out / "poses.jsonl")) == 45
    assert len(m["frames"]) == 2 and (out / "map.png").exists() and m["frames"][-1]["pose"]
    print("self-test OK:", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=300)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    out = a.out or Path(".artifacts/benben-runs") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if a.self_test:
        self_test(Path(".artifacts/benben-runs/self-test-" + str(int(time.time()))))
        sys.exit()
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} already has a run; pick a new --out")
    try:
        asyncio.run(record(a.seconds, out))
    except KeyboardInterrupt:
        pass
