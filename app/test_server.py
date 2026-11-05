"""Integration checks use generated evidence in temporary storage, never room photos."""
import base64
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import Store, create_server

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aP1sAAAAASUVORK5CYII=")


class AppTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = create_server(self.temp.name, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, path, body=None, headers=None):
        request = Request(self.url + path, data=None if body is None else json.dumps(body).encode(),
                          headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as response:
            return response.code, json.load(response)
        with response:
            if response.headers.get_content_type() == "application/json":
                return response.status, json.load(response)
            return response.status, response.read()

    def observation(self, **changes):
        data = {"title": "Test evidence", "notes": "Generated one-pixel test image",
                "observed_at": "2026-11-03T10:30:00-05:00", "image_base64": base64.b64encode(PNG).decode()}
        return {**data, **changes}

    def test_empty_workspace_and_static_assets(self):
        status, state = self.call("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(state["observations"], [])
        self.assertEqual(state["issues"], [])
        self.assertEqual(state["maps"], [])
        for path in ("/", "/styles.css", "/app.js", "/run.js"):
            self.assertEqual(self.call(path)[0], 200)

    def test_run_files_are_allow_listed_and_seekable(self):
        run = Path(self.temp.name) / "run"
        (run / "clips").mkdir(parents=True)
        (run / "clips/2-paper-bag.mp4").write_bytes(b"0123456789")
        (run / "manifest.json").write_text("{}")
        self.server.run_dir = run
        self.assertEqual(self.call("/run/clips/2-paper-bag.mp4"), (200, b"0123456789"))
        self.assertEqual(self.call("/run/clips/2-paper-bag.mp4", headers={"Range": "bytes=2-4"}), (206, b"234"))
        self.assertEqual(self.call("/run/clips/2-paper-bag.mp4", headers={"Range": "bytes=-3"}), (206, b"789"))
        self.assertEqual(self.call("/run/clips/2-paper-bag.mp4", headers={"Range": "bytes=20-"})[0], 416)
        for path in ("/run/manifest.json", "/run/../server.py", "/run/clips/other.mp4", "/run/lidar_iso.png"):
            self.assertEqual(self.call(path)[0], 404)

    def test_evidence_issue_map_and_persistence(self):
        status, map_record = self.call("/api/maps", {"name": "Test frame", "frame_id": "test_local"})
        self.assertEqual(status, 201)
        status, created = self.call("/api/observations", self.observation(map_id=map_record["id"], x_m=2, y_m=-1))
        self.assertEqual(status, 201)
        observation = self.call("/api/state")[1]["observations"][0]
        self.assertEqual(observation["observed_at"], "2026-11-03T15:30:00+00:00")
        self.assertEqual(observation["source"], "human_upload")
        self.assertEqual(observation["image_sha256"], hashlib.sha256(PNG).hexdigest())
        self.assertEqual(self.call(observation["image_url"]), (200, PNG))
        status, issue = self.call("/api/issues", {"observation_id": created["id"], "title": "Test follow-up"})
        self.assertEqual(status, 201)
        self.assertEqual(self.call(f"/api/issues/{issue['id']}/status", {"status": "resolved"})[0], 200)
        persisted = Store(self.temp.name).snapshot()
        self.assertEqual(persisted["issues"][0]["status"], "resolved")
        self.assertEqual(persisted["observations"][0]["map_id"], map_record["id"])

    def test_invalid_evidence_does_not_create_records(self):
        invalid = [self.observation(image_base64="not-base64"), self.observation(image_base64=base64.b64encode(b"<svg/>").decode()),
                   self.observation(observed_at="2026-11-03T10:00:00"), self.observation(x_m=1),
                   self.observation(map_id="missing", x_m=1, y_m=2), self.observation(title="")]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(self.call("/api/observations", payload)[0], 400)
        self.assertEqual(self.call("/api/state")[1]["observations"], [])
        self.assertEqual(list(self.server.store.images.iterdir()), [])

    def test_request_and_status_boundaries(self):
        self.assertEqual(self.call("/api/maps", {"name": "X", "frame_id": "x"}, {"Origin": "https://example.org"})[0], 403)
        self.assertEqual(self.call("/api/state", headers={"Host": "example.org"})[0], 403)
        self.assertEqual(self.call("/images/../watch.sqlite3")[0], 404)
        self.assertEqual(self.call("/api/issues/" + "0"*32 + "/status", {"status": "resolved"})[0], 404)
        self.assertEqual(self.call("/api/issues/" + "0"*32 + "/status", {"status": "invented"})[0], 400)
        self.assertEqual(self.call("/api/issues", {"observation_id": "missing", "title": "X"})[0], 400)


if __name__ == "__main__":
    unittest.main()


class CopilotTest(AppTest):
    def test_copilot_unconfigured_then_validated_with_stub(self):
        import os
        os.environ.pop("MODEL_API_KEY", None)
        status, created = self.call("/api/observations", self.observation())
        self.assertEqual(status, 201)
        ask = {"question": "Has the path been cleared?", "observationIds": [created["id"]]}
        self.assertEqual(self.call("/api/copilot/status")[1]["configured"], False)
        status, body = self.call("/api/copilot", ask)
        self.assertEqual((status, body["code"]), (503, "unconfigured"))
        sent = []
        def stub(body):
            sent.append(body)
            return {"text": "Not visible.", "evidenceRefs": [{"observationId": created["id"]}],
                    "evidenceState": "occluded", "proposedAction": "request_view", "claimVerdict": "insufficient"}
        self.server.copilot_provider = stub
        status, body = self.call("/api/copilot", ask)
        self.assertEqual(status, 200)
        self.assertEqual((body["provider"], body["evidenceState"], body["proposedAction"], body["claimVerdict"]),
                         ("meta", "occluded", "request_view", "insufficient"))
        self.assertEqual(body["evidenceRefs"], [{"observationId": created["id"]}])
        self.assertTrue(sent[0]["messages"][1]["content"][2]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.server.copilot_provider = lambda body: {**stub(body), "evidenceRefs": [{"observationId": "f" * 32}]}
        self.assertEqual(self.call("/api/copilot", ask)[0], 502)
        self.assertEqual(self.call("/api/copilot", {**ask, "observationIds": ["0" * 32]})[0], 404)
        self.assertEqual(self.call("/api/copilot", {**ask, "observationIds": []})[0], 400)

    def test_sam_boxes_parse_and_route(self):
        import copilot
        text = "<0f>0<|box;x1=181;y1=365;x2=556;y2=486;w=1516;h=1600;c=0.91|><|mask;x=0;y=0;data=abc|><|box;x1=9;y1=9;x2=5;y2=5;w=10;h=10|>"
        boxes = copilot.parse_sam_boxes(text)
        self.assertEqual(len(boxes), 1)  # the inverted box is dropped
        self.assertAlmostEqual(boxes[0]["x"], 181 / 1516)
        self.assertEqual(boxes[0]["confidence"], 0.91)
        status, created = self.call("/api/observations", self.observation())
        self.server.sam_provider = lambda body: text
        status, body = self.call("/api/segment", {"observationId": created["id"], "concept": "cart"})
        self.assertEqual((status, body["modelId"], len(body["boxes"])), (200, "sam-3.1", 1))
        self.assertEqual(self.call("/api/segment", {"observationId": created["id"], "concept": ""})[0], 400)
        self.assertEqual(self.call("/api/segment", {"observationId": [created["id"]], "concept": "cart"})[0], 400)

    def test_transcribe_route_checks_wav(self):
        import copilot, os
        os.environ.pop("MODEL_API_KEY", None)
        wav = b"RIFF" + b"\0" * 4 + b"WAVE" + b"\0" * 40
        body = {"audio_wav_base64": base64.b64encode(wav).decode()}
        self.assertEqual(self.call("/api/transcribe", body)[0], 503)
        self.server.asr_provider = lambda audio: "It's fixed." if audio == wav else ""
        status, answer = self.call("/api/transcribe", body)
        self.assertEqual((status, answer["text"], answer["modelId"]), (200, "It's fixed.", copilot.ASR_MODEL))
        self.assertEqual(self.call("/api/transcribe", {"audio_wav_base64": base64.b64encode(b"nope").decode()})[0], 400)


class SeedTest(unittest.TestCase):
    def test_seed_creates_observations_and_issue(self):
        from seed_shoot import seed
        with tempfile.TemporaryDirectory() as tmp:
            photo = f"{tmp}/p.png"
            open(photo, "wb").write(PNG)
            ids, issue = seed(f"{tmp}/ws", [(photo, "Cart on walkway", "2026-11-04T08:12:00-05:00"),
                                            (photo, "Far side", "2026-11-04T09:30:00-05:00")])
            state = Store(f"{tmp}/ws").snapshot()
            self.assertEqual((len(ids), len(state["observations"]), state["issues"][0]["id"]), (2, 2, issue))
            self.assertEqual(state["issues"][0]["observation_id"], ids[0])

