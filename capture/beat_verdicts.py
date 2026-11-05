"""Ask Muse Spark to triage chosen BenBen frames: obstacle, who it affects, and one action.

    MODEL_API_KEY=... SSL_CERT_FILE=/etc/ssl/cert.pem python3 capture/beat_verdicts.py <run> 10 26 49 ...

Writes <run>/verdicts.json (one record per frame: model, latency, the frame's capture time and Muse's answer).
"""
import base64
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import copilot  # noqa: E402

PROMPT = """You are BenBen, a quadruped robot inspecting a residential estate's walking route at night. A person drove you; you only report.
Look at this camera frame from your own camera (low, about 30 cm high, lit by a hand torch). Decide:
- obstacle: what, if anything, affects someone getting along this route (say "none" if the way is fine).
- kind: none, temporary (movable: litter, bag, chair, leaves), fixed_defect (steps without a ramp, missing curb ramp, rough or broken pavement, gappy railing), or unclear.
- affects: which of wheelchair, crutches, cane, stroller, children are affected.
- action: exactly one of none, reroute (a step-free alternative is needed), flag_for_service (temporary, grounds staff can clear it), report_issue (fixed defect, open a maintenance issue), needs_human (unclear or someone's belongings).
- reason: one plain sentence a resident would understand, about what you can actually see. If the frame is too dark or blurred to tell, say so and choose needs_human."""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["obstacle", "kind", "affects", "action", "reason"], "properties": {
    "obstacle": {"type": "string"},
    "kind": {"type": "string", "enum": ["none", "temporary", "fixed_defect", "unclear"]},
    "affects": {"type": "array", "items": {"type": "string", "enum": ["wheelchair", "crutches", "cane", "stroller", "children"]}},
    "action": {"type": "string", "enum": ["none", "reroute", "flag_for_service", "report_issue", "needs_human"]},
    "reason": {"type": "string"}}}


def judge(run, frame):
    meta = json.loads((run / "manifest.json").read_text())["frames"][frame]
    image = base64.b64encode((run / meta["file"]).read_bytes()).decode()
    body = {"model": copilot.MODEL, "max_tokens": 4000, "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}}]}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "triage", "schema": SCHEMA}}}
    started = time.monotonic()
    try:
        answer = copilot.call_meta(body)
    except copilot.ProviderError as e:  # one empty reply shouldn't sink the batch
        answer = {"obstacle": "", "kind": "unclear", "affects": [], "action": "needs_human", "reason": f"(no answer: {e})"}
    return {"frame": frame, "file": meta["file"], "captured_at": meta["at"], "model": copilot.MODEL,
            "latency_ms": round((time.monotonic() - started) * 1000), "answer": answer}


if __name__ == "__main__":
    run, frames = Path(sys.argv[1]), [int(f) for f in sys.argv[2:]]
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda f: judge(run, f), frames))
    (run / "verdicts.json").write_text(json.dumps(results, indent=2))
    for r in results:
        a = r["answer"]
        print(f"#{r['frame']:3d} {a['action']:16s} {a['kind']:12s} {r['latency_ms']:5d}ms  {a['reason']}")
