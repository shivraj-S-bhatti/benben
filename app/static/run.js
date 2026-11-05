"use strict";
// BenBen inspection run 20261105T002653Z: action items, LiDAR twin and clips. Read-only; files come from /run/.
(() => {
  const $ = (s) => document.querySelector(s);
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
  const ET = {timeZone: "America/New_York"};
  const etTime = (iso) => new Date(iso).toLocaleTimeString("en-US", {...ET, hour: "numeric", minute: "2-digit", second: "2-digit"}) + " ET";
  const RUN_START = "2026-11-05T00:26:53Z";

  // Stills with a definite action, plus one Muse could not read. Pin spots: iso is placed by hand from landmarks on
  // lidar_iso.png; top is BenBen's logged pose for that still on map.png (40 px/m). Percent of image width/height.
  const PICK = [
    {frame: 10, clip: 0, iso: [23.8, 66.1], top: [20.2, 43.4]},
    {frame: 26, clip: null, iso: [12.1, 71.0], top: [9.7, 41.5]},
    {frame: 48, clip: 1, iso: [50.7, 60.0], top: [39.7, 56.6]},
    {frame: 144, clip: 2, iso: [45.9, 55.5], top: [41.6, 44.5]},
    {frame: 160, clip: 3, iso: [44.4, 52.0], top: [44.3, 36.9]},
    {frame: 224, clip: null, iso: [39.7, 43.8], top: [49.8, 18.4]},
  ];
  const ACTION = {reroute: ["Reroute", "red"], flag_for_service: ["Flag for service", "amber"], report_issue: ["Report an issue", "teal"], needs_human: ["Needs a human", "ink"]};
  const CLIPS = [
    ["clips/1-steps-no-ramp.mp4", "Steps, no ramp"],
    ["clips/2-paper-bag.mp4", "Paper bag"],
    ["clips/3-chair-laptop.mp4", "Chair and laptop"],
    ["clips/4-entrance-step.mp4", "Entrance step"],
    ["lidar_split.mp4", "Camera + LiDAR"],
  ];
  const VIEWS = {
    iso: {src: "/run/lidar_iso.png", note: "BenBen's LiDAR map, isometric. Pins placed by hand, approximate."},
    top: {src: "/run/map.png", note: "BenBen's LiDAR map, top-down. Pins at BenBen's logged pose for each still."},
  };
  const state = {items: [], sel: null, view: "iso", clip: 0};

  function selectClip(i, play) {
    state.clip = i;
    const player = $("#player");
    player.src = "/run/" + CLIPS[i][0];
    if (play) player.play().catch(() => {});
    for (const [j, b] of [...$("#clip-list").children].entries()) b.setAttribute("aria-pressed", String(j === i));
    $("#clip-note").textContent = `BenBen camera, human-piloted · ${CLIPS[i][1]}${i === 4 ? " (camera beside the LiDAR view)" : ""}`;
  }

  function select(frame) {
    state.sel = frame;
    const item = state.items.find((x) => x.frame === frame);
    for (const n of document.querySelectorAll("[data-frame]")) n.classList.toggle("on", Number(n.dataset.frame) === frame);
    $(`.wb-card[data-frame="${frame}"]`)?.scrollIntoView({block: "nearest", behavior: "smooth"});
    if (item && item.clip !== null && item.clip !== state.clip) selectClip(item.clip, true);
  }

  function renderPins() {
    const view = VIEWS[state.view], frame = $("#twin-frame");
    $("#twin-img").src = view.src;
    frame.classList.toggle("is-top",state.view === "top");
    $("#twin-note").textContent = view.note;
    for (const id of ["iso", "top"]) $(`#view-${id}`).setAttribute("aria-pressed", String(id === state.view));
    frame.querySelectorAll(".pin").forEach((p) => p.remove());
    state.items.forEach((item, i) => {
      const [x, y] = item[state.view];
      const pin = el("button", `pin ${item.tone}`, String(i + 1));
      pin.type = "button";
      pin.dataset.frame = item.frame;
      pin.style.left = x + "%"; // CSSOM: the CSP blocks style attributes, not property writes
      pin.style.top = y + "%";
      pin.setAttribute("aria-label", `${i + 1}: ${item.label}, ${item.answer.obstacle}`);
      pin.title = `${item.label}: ${item.answer.obstacle}`;
      pin.addEventListener("click", () => select(item.frame));
      frame.append(pin);
    });
    if (state.sel !== null) select(state.sel);
  }

  function renderItems() {
    const list = $("#action-list");
    list.replaceChildren(...state.items.map((item, i) => {
      const card = el("li", "wb-card");
      card.dataset.frame = item.frame;
      card.tabIndex = 0;
      const head = el("div", "wb-card-head");
      head.append(el("span", `num ${item.tone}`, String(i + 1)), el("time", "", etTime(item.captured_at)), el("span", "meta", `still ${String(item.frame).padStart(3, "0")}`));
      const thumb = el("img", "thumb");
      thumb.src = "/run/" + item.file;
      thumb.alt = `BenBen camera still ${item.frame}`;
      thumb.loading = "lazy";
      const body = el("div", "wb-card-body");
      body.append(el("p", "obstacle", item.answer.obstacle), el("p", "line", `“${item.answer.reason}”`));
      const foot = el("div", "wb-card-foot");
      foot.append(el("span", `chip act ${item.tone}`, item.label), el("span", "model", `${item.model} · ${(item.latency_ms / 1000).toFixed(1)} s`));
      card.append(head, thumb, body, foot);
      card.addEventListener("click", () => select(item.frame));
      card.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(item.frame); } });
      return card;
    }));
    $("#items-count").textContent = `${state.items.length} from ${state.answered} Muse answers`;
  }

  async function load() {
    $("#run-name").textContent = new Date(RUN_START).toLocaleString("en-US", {...ET, month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit"}) + " ET";
    const clipList = $("#clip-list");
    CLIPS.forEach(([, label], i) => {
      const b = el("button", "", label);
      b.type = "button";
      b.addEventListener("click", () => selectClip(i, true));
      clipList.append(b);
    });
    selectClip(0, false);
    $("#view-iso").addEventListener("click", () => { state.view = "iso"; renderPins(); });
    $("#view-top").addEventListener("click", () => { state.view = "top"; renderPins(); });

    const passes = await Promise.all(["/run/verdicts-pass1.json", "/run/verdicts-pass2.json"].map((u) => fetch(u).then((r) => {
      if (!r.ok) throw Error(`${u} returned ${r.status}`);
      return r.json();
    })));
    const answers = new Map(passes.flat().map((v) => [v.frame, v]));
    state.answered = passes.flat().length;
    state.items = PICK.flatMap((p) => {
      const v = answers.get(p.frame);
      if (!v) return [];
      const unclear = v.answer.kind === "unclear";
      const [label, tone] = unclear ? ["Too dark to tell, needs another look", "ink"] : ACTION[v.answer.action] ?? [v.answer.action, "ink"];
      return [{...p, ...v, label, tone}];
    }).sort((a, b) => a.captured_at.localeCompare(b.captured_at));
    renderItems();
    renderPins();
  }

  load().catch((error) => {
    $("#action-list").replaceChildren(el("li", "wb-empty", `Could not load the BenBen run: ${error.message}. Start the server with --run-dir pointing at the run folder.`));
    renderPins();
  });
})();
