"""Claim-vs-fresh-view verdict eval: how often would the model wrongly close an issue?

Manifest CSV columns: claim, before_image, fresh_image, label (supported | contradicted | insufficient).
Image paths are relative to the manifest. Label every row by hand before running anything.

    python3 app/verdict_eval.py path/to/manifest.csv            # live: one Meta call per row
    python3 app/verdict_eval.py path/to/manifest.csv --fresh-only  # baseline: no memory photo
    python3 app/verdict_eval.py --self-test                      # stub provider, no network

Live runs read MODEL_API_KEY from the environment and send each row's photos to Meta's API.
"""
import argparse
import base64
import csv
import sys
from collections import Counter
from pathlib import Path

import copilot

VERDICTS = ("supported", "contradicted", "insufficient")
SCHEMA = {"type": "object", "properties": {"verdict": {"type": "string", "enum": list(VERDICTS)}, "reason": {"type": "string"}},
          "required": ["verdict", "reason"]}
PROMPT = ("A person claims: \"{claim}\". {memory}The last image is a fresh view taken after the claim. Decide whether the "
          "fresh view supports the claim, contradicts it, or is insufficient (wrong angle, occluded, too dark). Prefer "
          "'insufficient' over guessing. Reply with a verdict and a one-sentence reason about what is visible.")


def image_part(path):
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}[path.suffix.lower()]
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"}}


def judge(row, root, fresh_only, provider):
    memory = "" if fresh_only else "The first image is the earlier recorded observation of the same spot. "
    parts = [{"type": "text", "text": PROMPT.format(claim=row["claim"], memory=memory)}]
    if not fresh_only:
        parts.append(image_part(root / row["before_image"]))
    parts.append(image_part(root / row["fresh_image"]))
    answer = provider({"model": copilot.MODEL, "max_tokens": 2000, "messages": [{"role": "user", "content": parts}],
                       "response_format": {"type": "json_schema", "json_schema": {"name": "verdict", "schema": SCHEMA}}})
    if not isinstance(answer, dict) or answer.get("verdict") not in VERDICTS:
        raise copilot.ProviderError("answer had no valid verdict")
    return answer["verdict"]


def score(pairs):
    """pairs: [(label, predicted)]. A false close is 'supported' predicted when the truth is not supported."""
    confusion = Counter(pairs)
    total = len(pairs)
    false_close = sum(n for (label, pred), n in confusion.items() if pred == "supported" and label != "supported")
    return {"n": total, "accuracy": sum(n for (l, p), n in confusion.items() if l == p) / total if total else 0.0,
            "false_closes": false_close, "not_supported": sum(1 for l, _ in pairs if l != "supported"),
            "abstained": sum(1 for _, p in pairs if p == "insufficient"), "confusion": confusion}


def report(result, label):
    print(f"{label}: n={result['n']} accuracy={result['accuracy']:.0%} "
          f"false closes={result['false_closes']}/{result['not_supported']} abstained={result['abstained']}")
    print("            " + " ".join(f"{v[:6]:>7}" for v in VERDICTS) + "   <- predicted")
    for truth in VERDICTS:
        print(f"{truth:>12}" + " ".join(f"{result['confusion'][(truth, p)]:>7}" for p in VERDICTS))


def self_test():
    assert score([("contradicted", "supported"), ("supported", "supported"), ("insufficient", "insufficient")]) \
        ["false_closes"] == 1
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aP1sAAAAASUVORK5CYII=")
        (root / "a.png").write_bytes(png)
        sent = []
        stub = lambda body: sent.append(body) or {"verdict": "contradicted", "reason": "cart visible"}
        row = {"claim": "the path is clear", "before_image": "a.png", "fresh_image": "a.png", "label": "contradicted"}
        assert judge(row, root, False, stub) == "contradicted" and len(sent[0]["messages"][0]["content"]) == 3
        assert judge(row, root, True, stub) == "contradicted" and len(sent[1]["messages"][0]["content"]) == 2
    print("self-test ok")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", nargs="?", type=Path)
    parser.add_argument("--fresh-only", action="store_true", help="baseline without the earlier observation")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.manifest:
        parser.error("give a manifest CSV or --self-test")
    rows = list(csv.DictReader(args.manifest.open()))
    bad = [r for r in rows if r.get("label") not in VERDICTS]
    if bad:
        sys.exit(f"{len(bad)} rows have a label outside {VERDICTS}")
    pairs, errors = [], 0
    for i, row in enumerate(rows, 1):
        try:
            predicted = judge(row, args.manifest.parent, args.fresh_only, copilot.call_meta)
        except copilot.ProviderError as error:  # an error is not a prediction: excluded from scoring, reported
            print(f"row {i}: ERROR {error}", file=sys.stderr)
            errors += 1
            continue
        pairs.append((row["label"], predicted))
        print(f"row {i}: label={row['label']} predicted={predicted}")
    report(score(pairs), "fresh view only" if args.fresh_only else "memory + fresh view")
    if errors:
        print(f"errors={errors} rows excluded from the scores above")


if __name__ == "__main__":
    main()
