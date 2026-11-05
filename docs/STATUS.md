# Status, Nov 4 2026

Three states. **Ran live**: on the real robot or the real Meta API on Nov 4. **Wired**: the code exists and passes offline tests but has not run against the real thing. **Roadmap**: not built. Times are US Eastern.

| Piece | State | Evidence |
|---|---|---|
| Listen-only WebRTC link to BenBen | Ran live | Connects in about 3 s over BenBen's hotspot. Sends no motor, mode or stand commands. |
| Camera, LiDAR and pose recording | Ran live | 7:27 to 7:31 PM run, outdoors after dark, Shivraj driving with the remote: 3,396 video frames, 2,355 LiDAR clouds, 227 stills with poses, and a top-down map with the driven path. Pose streams at about 19 Hz. |
| Camera/LiDAR split video and isometric LiDAR view | Ran | `render_lidar.py` on that run: `lidar_split.mp4` and `lidar_iso.png`. |
| Muse Spark triage (`muse-spark-1.3`) | Ran live | 14 stills judged at 7:50 PM: 1 reroute, 2 flag for service, 1 report an issue, 10 needs a human (8 of them too dark to tell). 7 to 38 s per frame. Saved as `verdicts-pass1.json` and `verdicts-pass2.json`. |
| SAM 3.1 boxes (`sam-3.1`) | Ran live | 8 requests on 6 stills, 0.8 to 2.4 s each. 7 returned a box; "chair" on frame 144 returned none, while "laptop" on the same frame did. Saved as `sam.json` in the run folder. |
| Workbench dashboard | Ran locally | Shows the run's action items, LiDAR map, clips and Muse answers from the run folder. |
| Recorder self-test | Passes | `record.py --self-test`, offline: 45 frames decode, 15 clouds, 45 poses, map and manifest. |
| App tests | Pass | 14 tests, stub providers, no network. |
| Ask-Muse in the dashboard (`/api/copilot`) | Wired | Tested with stubs. The key answered a text-only smoke test in 2.2 s; a photo question through the dashboard is not recorded. |
| SAM button in the dashboard (`/api/segment`) | Wired | Tested with stubs. The live SAM calls above went to the same model outside the dashboard. |
| Voice Transcribe (`muse-voice-transcribe-1.0`) | Wired | Tested with a stub only. |
| Muse Spark Open on Baseten | Wired | Fallback provider; never called. |
| Importing a run into the evidence store | Wired | `import_capture.py` is tested offline; an import of the Nov 4 run is not recorded. |
| DimOS recording export | Wired | `export_run.py` reads DimOS recordings; DimOS replay works on the Mac. |
| DimOS live connection | Failed | Hung for over two minutes on Nov 4; dropped. |
| Route patrol, planning, any motion | Roadmap | See [autonomy/README.md](../autonomy/README.md). BenBen was driven by hand for the whole demo. |

In the dark, the camera alone was not enough: 8 of the 14 Muse answers said the frame was too dark to judge. The LiDAR recorded the same stretches.
