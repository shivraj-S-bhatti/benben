# BenBen pitch visuals: shared design system

Shared by the hero graphic and the one-pagers. Each page is one self-contained HTML file, rendered to PNG (and PDF for one-pagers) with headless Chrome.

## Background: multimodal halftone gradient

- Base: a mesh of layered radial gradients over deep ink `#0b1220`. Teal `#14b8a6` (camera), amber `#f59e0b` (decisions), violet `#6d5bd0` (memory/twin) and blue `#3b82f6` (LiDAR) blobs at different positions, 35–55% opacity.
- Halftone: a dot grid (about 6–8 px pitch) masked so dot size and opacity follow the gradient. Big dots where the colour is strong, fading to none. Use an SVG `<pattern>` plus a mask, or CSS `radial-gradient` repeats with `mask-image`. It should read as print halftone, not noise.
- Keep the centre calmer so the text stays legible.

## Glass cards

- Fill `rgba(255,255,255,0.08)` to `0.12`, `backdrop-filter: blur(18px) saturate(140%)`, and a 1 px border `rgba(255,255,255,0.22)`.
- A faint top-edge highlight, 20 px radius and a soft shadow `0 20px 60px rgba(0,0,0,0.35)`.
- Text inside: `#f5f7fa` for body, `rgba(245,247,250,0.7)` for secondary.

## Type (local files only, no web fonts)

- Headlines: Instrument Serif, `app/static/fonts/InstrumentSerif-Regular.ttf`.
- Everything else: Inter, `app/static/fonts/Inter-Latin.woff2`.
- Reference both by relative path from the HTML file.

## Shared legends

- **Status:** ● ran Nov 4 · ◐ wired, tested offline · ○ roadmap.
- **Actions:** amber Reroute · teal Flag for service · red Report an issue · grey Needs a human.

## Honesty rules

- Real numbers only from `docs/STATUS.md`, `README.md` and the run facts below. Anything you're unsure of gets a *.
- Nothing claims autonomy today. Tonight a human drove BenBen.
- 2032 content is a vision. Label it as one, and put no invented statistics in it.

## Nov 4 run facts (verified)

- Night run of about 4 min, human-piloted with the remote.
- Recorded 3,396 video frames, 2,355 LiDAR clouds (5 cm voxels, about 10 Hz), pose at about 19 Hz, and 227 stills.
- Muse Spark (`muse-spark-1.3`) judged 14 stills: 1 reroute (steps, no ramp), 2 flag for service (paper bag), 1 report an issue (raised entrance step), and 10 needs a human, 8 of them "too dark".
- Muse latency was 7–43 s per frame (run files). SAM 3.1 was live at 0.8–2.4 s per frame and outlined the stairs, the bag, the chair and the entrance step.
- Indoor twin: MapAnything ran on 32 frames in 122 s on an M1 Pro (4.2M points), and a Brush Gaussian splat reached 17 dB PSNR on held-out views.

## Real images (copy small JPEG/PNG versions into `docs/onepagers/assets/`)

Run folder: `/Users/apple/Projects/robotics/video-to-gym-lab/.artifacts/benben-runs/20261105T002653Z/`

- `frames/010.jpg`: steps with pumpkins, no ramp.
- `frames/048.jpg`: paper bag.
- `frames/143.jpg`: chair with laptop.
- `frames/160.jpg`: entrance step.
- `frames/022.jpg`: dark railing.
- `lidar_iso.png`: isometric LiDAR map of the route.
- `map.png`: the top-down map.
- `beats/b2-bag.json` and similar: SAM boxes and Muse answers.

Also:

- The LiDAR split frame: `split_60s.jpg` in the same run folder.
- The workbench: `/Users/apple/Projects/robotics/video-to-gym-lab/.artifacts/final/workbench.png`.
- `docs/turbo/assets/twin-and-dog.png` and `benben-loop.png` in this repo.

**Do not use** frames 209–226 (indoor clutter and a person), or the MapAnything cloud, which shows a person in one stretch.

---

# v2 house style (supersedes the colour, type and glass rules above; the facts and image rules still apply)

Mood: an editorial engineering document. Calm and confident, mostly paper and ink, with red used sparingly and only where the reader should look. Every colour is impure (warm, slightly dirty), and tone comes from gradation, not hue.

**Palette** (tune by eye, don't treat these as exact)
- Inks: `#141312`, `#1e1c1a` and `#2a2724` for dark panels and headings.
- Greys: `#4a4642`, `#77726b` and `#a39d94` for secondary text and hairlines.
- Dirty whites, used as the page and cards: `#e9e4db`, `#efebe4`, `#f5f2ec` and `#ddd6ca`.
- Reds: `#c7372a` as the signal, `#8f2a20` deep and `#e0786b` muted. Use red for one or two things per view.
- An optional warm khaki `#b3a37f` for a "done or historical" tone.

**Texture:** a faint paper grain and a very light engineering grid (about 24 px). A halftone in grey only is allowed, for gradation in large areas. No glass, no neon, no blur.

**Type**
- Display: a tight grotesk. On macOS use "Helvetica Neue" bold, condensed letter-spacing (-0.02em), or DIN Condensed for big numbers.
- Labels: monospace uppercase, tracked +0.08em ("SF Mono", then Menlo).
- Body: Inter (`app/static/fonts/Inter-Latin.woff2`).
- No serif.

**Shapes:** flat cards with 1 px hairlines, square or 2 px corners, and dark ink panels for emphasis. Status chips are small and boxed.

**Legends**
- Status: ● ran Nov 4 (solid ink) · ◐ wired · ○ roadmap.
- Actions: Report an issue = red · Reroute = ink · Flag for service = khaki · Needs a human = hollow grey.

**Words:** cut ruthlessly. A label beats a sentence, a number beats a label. Every sentence must earn its place; no stacked qualifiers. Load the `quill:polish` skill (or `quill:core`) for the tell sweep on all copy.
