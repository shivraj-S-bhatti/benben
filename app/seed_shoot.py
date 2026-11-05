"""Load real shoot photos into a fresh workspace before recording, so nobody types forms on camera.

    python3 app/seed_shoot.py --data-dir .artifacts/demo-workspace \\
      --photo .artifacts/shoot/before.jpg  --title "Cart across the step-free walkway" --at 2026-11-04T08:12-05:00 \\
      --photo .artifacts/shoot/latest.jpg  --title "Walkway from the far side (latest)" --at 2026-11-04T09:30-05:00
    python3 app/server.py --data-dir .artifacts/demo-workspace

Photos go through the same Store.create_observation path as uploads (same checks, hashes and size limit).
The first photo also opens an issue. Times are what you enter: say so if asked. Add the fresh photo live in the app.
"""
import argparse
import base64
from pathlib import Path

from server import Store


def seed(directory, entries, issue_title=None):
    store = Store(directory)
    ids = [store.create_observation({"title": title, "observed_at": at, "notes": "",
                                     "image_base64": base64.b64encode(Path(photo).read_bytes()).decode()})["id"]
           for photo, title, at in entries]
    issue = store.create_issue({"observation_id": ids[0], "title": issue_title or entries[0][1]})["id"] if ids else None
    return ids, issue


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--photo", action="append", required=True)
    parser.add_argument("--title", action="append", required=True)
    parser.add_argument("--at", action="append", required=True, help="timezone-aware ISO time the photo was taken")
    parser.add_argument("--issue", help="issue title (defaults to the first photo's title)")
    args = parser.parse_args()
    if not len(args.photo) == len(args.title) == len(args.at):
        parser.error("give one --title and one --at for every --photo")
    if (args.data_dir / "watch.sqlite3").exists():
        parser.error(f"{args.data_dir} already has a workspace; pick a new folder so the demo starts clean")
    ids, issue = seed(args.data_dir, list(zip(args.photo, args.title, args.at)), args.issue)
    print(f"Seeded {len(ids)} observations and 1 issue ({issue}) into {args.data_dir}")


if __name__ == "__main__":
    main()
