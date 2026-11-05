# Figures

**`assets/benben-loop.svg`** (PNG at 2x beside it): the most ambitious loop we know is buildable. The top row is one run, left to right: question, Muse Spark workflow plan, route and checkpoints, BenBen drives, sense, perceive and decide (four action outputs), then review and act. The bottom row is what every run feeds, right to left: run archive, virtual twin, place memory, world map, replay evaluations, then a navigation policy that is promoted only if it beats the current one. Yellow edges carry compute, blue edges carry sensor and robot data, and the long bottom edge sends the question back until a later visit verifies it.

**Status dots** on every card: solid = ran on Nov 4 (sense, perceive + decide, run archive, LiDAR voxel twin, MapAnything indoor cloud, Brush splat indoor); half = wired and tested offline (review → act UI, ask-Muse); hollow = roadmap (Muse workflow planning, DimOS route following, place memory, world map, evaluations, VLA). "BenBen drives" carries two dots: remote driving ran, the fixed-route planner is roadmap.

**`assets/twin-and-dog.svg`** (PNG at 2x beside it): an illustration of BenBen, a generic Go2-style quadruped with a LiDAR dome, standing on a slab of LiDAR points with a raised step, a curb edge and a railing. It shows the teal driven path, the scan fan reaching the step and four finding pins in the action colours: amber Reroute, teal Flag for service, red Report an issue, grey Needs a human. It is not a render of the Nov 4 capture.

The action colours match across both figures.
