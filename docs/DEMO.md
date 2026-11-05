# The 2-minute demo

BenBen inspects an estate's walking route, and every finding ends in one action: reroute, flag for service, report an issue, or hand it to a person. Footage is from the Nov 4 night run (7:27 to 7:31 PM ET), with Shivraj driving. The Muse lines are Muse Spark's actual answers (`muse-spark-1.3`) on those frames, saved in the run folder as `verdicts-pass1.json` and `verdicts-pass2.json`.

| Time | Picture | Voice |
|---|---|---|
| 0:00 | Shivraj at the desk, the window onto the path | "I got injured and ended up in a wheelchair. I take public transport, and I realized I had no idea if my route to the bus was even passable." |
| 0:15 | The spot outside | "From my desk I watch people struggle at this exact spot. I've seen people fall here." |
| 0:25 | BenBen indoors, walking to the door | "BenBen used to inspect hard-to-reach places in a warehouse. It was retired because it needed a human operator. Tonight I still drove it." |
| 0:35 | Steps to a doorway (clip `1-steps-no-ramp`, frame 10) | Muse: "You can see concrete steps with large pumpkins and plant pots leading up to the lit white door and no ramp." → **Reroute** |
| 0:50 | Bag on the path (`2-paper-bag`, frame 48) | Muse: "A large white paper bag is sitting on the footpath beside grass and a tree." → **Flag for service** |
| 1:00 | Raised step at an entrance (`4-entrance-step`, frame 160) | Muse: "There is a raised concrete step up to the white doors against the brick wall with no ramp visible." → **Report an issue** |
| 1:10 | Chair with a laptop (`3-chair-laptop`, frame 144) | Muse: "A folding chair with a laptop on it is blocking the path to the front door." → **Needs a human** |
| 1:20 | Railing, road edge, leaves (frames 21, 26, 76, 117, 133) | Muse: "The frame is too dark to tell…" → **Needs a human** |
| 1:30 | Split screen, camera left, LiDAR right (`lidar_split.mp4`) | "In the dark the camera barely sees. The LiDAR still sees every step and edge." |
| 1:45 | Dashboard: each finding with its time, photo and action | "Muse Spark judges the photos, SAM 3.1 outlines the obstacle, and each finding cites its frame." |
| 1:55 | Close | "Great routing apps exist. They're only as good as their map. BenBen keeps the map true." |

## Rules for the cut

- Say that a person drove BenBen. "We told it to go look at the stairs" reads as if it drove itself.
- Muse took 7 to 38 seconds per frame. Speed up or cut the wait.
- Say "there's no curb ramp" at the road edge unless someone has checked that the map shows a crossing there.
- "I've seen people fall here" is Shivraj's own observation; keep it in his voice.
