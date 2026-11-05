"""Render a BenBen run as a side-by-side video: camera on the left, an isometric LiDAR view on the right.

    python capture/render_lidar.py .artifacts/benben-runs/<run> [--speed 2]

Writes <run>/lidar_split.mp4 and <run>/lidar_iso.png (the whole run from above at an angle). Grey = everything mapped
so far, coloured by height; teal = what the LiDAR sees right now; amber = the path driven; red = BenBen.
"""
import argparse
import json
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

VOX, W, H, FPS = 0.05, 1920, 1080, 15
YAW, TILT = np.deg2rad(45), np.deg2rad(35)


def jsonl(p):
    return [json.loads(line) for line in open(p)]


def iso(xyz):
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    u = x * np.cos(YAW) - y * np.sin(YAW)
    v = x * np.sin(YAW) + y * np.cos(YAW)
    return np.stack([u, -(v * np.sin(TILT)) - z * np.cos(TILT)], 1)


def main(run, speed):
    clouds, poses, vframes = jsonl(run / "lidar.jsonl"), jsonl(run / "poses.jsonl"), jsonl(run / "video_frames.jsonl")
    sample = np.concatenate([np.load(run / "lidar" / f"{c['i']:06d}.npy") for c in clouds[::25]])
    sample = sample[(sample[:, 2] > -0.5) & (sample[:, 2] < 2.5)]
    lo3 = np.floor(sample.min(0) / VOX).astype(int) - 40
    dims = np.ceil(sample.max(0) / VOX).astype(int) + 40 - lo3
    occ = np.zeros(dims, bool)
    pr = iso(sample)
    plo, phi = np.percentile(pr, 0.5, 0), np.percentile(pr, 99.5, 0)
    pane_w, pane_h = W // 2, H
    scale = 0.92 * min(pane_w / (phi[0] - plo[0]), pane_h / (phi[1] - plo[1]))
    off = np.array([pane_w, pane_h]) / 2 - (plo + phi) / 2 * scale

    def to_px(pts2):
        return (pts2 * scale + off).astype(int)

    path_xyz = np.array([p["pose"][:3] for p in poses])
    path_ts = np.array([p["ts"] for p in poses])
    font = ImageFont.load_default(size=28) if hasattr(ImageFont, "load_default") else None

    out = av.open(str(run / "lidar_split.mp4"), "w")
    st = out.add_stream("h264_videotoolbox", rate=FPS)
    st.width, st.height, st.pix_fmt = W, H, "yuv420p"
    st.bit_rate = 8_000_000
    st.codec_context.time_base = Fraction(1, FPS)

    t0, t_end = max(clouds[0]["ts"], vframes[0]["ts"]), min(clouds[-1]["ts"], vframes[-1]["ts"])
    vin = av.open(str(run / "video.mp4"))
    vdec = vin.decode(video=0)
    vi, cam = -1, None
    ci, cur = -1, np.zeros((0, 3), np.float32)
    acc = []
    k = 0
    while True:
        t = t0 + k * speed / FPS
        if t > t_end:
            break
        while vi + 1 < len(vframes) and vframes[vi + 1]["ts"] <= t:
            vi += 1
            cam = next(vdec).to_image()
        while ci + 1 < len(clouds) and clouds[ci + 1]["ts"] <= t:
            ci += 1
            cur = np.load(run / "lidar" / f"{ci:06d}.npy")
            cur = cur[(cur[:, 2] > -0.5) & (cur[:, 2] < 2.5)]
            idx = np.clip(np.round(cur / VOX).astype(int) - lo3, 0, dims - 1)
            new = ~occ[idx[:, 0], idx[:, 1], idx[:, 2]]
            occ[idx[new, 0], idx[new, 1], idx[new, 2]] = True
            acc.append(cur[new])
        frame = np.full((H, W, 3), 14, np.uint8)
        pane = frame[:, W // 2:]
        if acc:
            allp = np.concatenate(acc)
            px = to_px(iso(allp))
            ok = (px[:, 0] >= 0) & (px[:, 0] < pane_w) & (px[:, 1] >= 0) & (px[:, 1] < pane_h)
            g = (70 + 150 * np.clip((allp[ok, 2] + 0.3) / 1.8, 0, 1)).astype(np.uint8)
            pane[px[ok, 1], px[ok, 0]] = np.stack([g, g, g], 1)
        if len(cur):
            px = to_px(iso(cur))
            ok = (px[:, 0] >= 0) & (px[:, 0] < pane_w) & (px[:, 1] >= 0) & (px[:, 1] < pane_h)
            pane[px[ok, 1], px[ok, 0]] = (45, 212, 191)
        img = Image.fromarray(frame)
        d = ImageDraw.Draw(img)
        upto = path_xyz[path_ts <= t]
        if len(upto) > 1:
            pp = to_px(iso(upto)) + [W // 2, 0]
            d.line([tuple(p) for p in pp], fill=(245, 158, 11), width=4)
            x, y = pp[-1]
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(239, 68, 68))
        if cam is not None:
            c = cam.resize((W // 2 - 40, int((W // 2 - 40) * cam.height / cam.width)))
            img.paste(c, (20, (H - c.height) // 2))
        d.text((24, 24), "BenBen camera", fill=(240, 240, 240), font=font)
        d.text((W // 2 + 24, 24), "BenBen LiDAR (live scan teal, path amber)", fill=(240, 240, 240), font=font)
        d.text((24, H - 50), f"human-piloted · {speed:g}x · t+{t - t0:5.1f}s", fill=(160, 160, 160), font=font)
        vf = av.VideoFrame.from_image(img).reformat(format="yuv420p")
        vf.pts = k
        for p in st.encode(vf):
            out.mux(p)
        k += 1
    for p in st.encode():
        out.mux(p)
    out.close()
    final = np.concatenate(acc)
    px = to_px(iso(final))
    ok = (px[:, 0] >= 0) & (px[:, 0] < pane_w) & (px[:, 1] >= 0) & (px[:, 1] < pane_h)
    still = np.full((pane_h, pane_w, 3), 250, np.uint8)
    g = (40 + 120 * (1 - np.clip((final[ok, 2] + 0.3) / 1.8, 0, 1))).astype(np.uint8)
    still[px[ok, 1], px[ok, 0]] = np.stack([g, g, g + 8], 1)
    si = Image.fromarray(still)
    ImageDraw.Draw(si).line([tuple(p) for p in to_px(iso(path_xyz))], fill=(15, 118, 110), width=4)
    si.save(run / "lidar_iso.png")
    print(f"{k} frames ({k / FPS:.0f}s at {speed:g}x), {len(final)} voxels -> {run}/lidar_split.mp4, lidar_iso.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--speed", type=float, default=2)
    a = ap.parse_args()
    main(a.run, a.speed)
