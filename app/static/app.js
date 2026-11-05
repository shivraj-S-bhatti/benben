"use strict";
// Maintenance Watch: real workspace (backend API) + scripted walkthrough (in-memory only).
const $ = (s) => document.querySelector(s);
const STATUS_NAMES = {new: "New", acknowledged: "Acknowledged", in_progress: "In progress", resolved: "Resolved", dismissed: "Dismissed"};
const OPEN = (issue) => !["resolved", "dismissed"].includes(issue.status);

function h(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "html") node.innerHTML = value; // only for our own static SVG strings
    else if (key === "style") node.style.cssText = value; // CSSOM: the server CSP blocks style attributes
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  node.append(...kids.flat().filter((k) => k !== null && k !== undefined && k !== false));
  return node;
}
const icon = (name) => h("span", {class: "ico", html: `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`});
const speaker = (name, note) => h("span", {class: "speaker"}, h("strong", {text: name}), note ? ` · ${note}` : "");
const chip = (text, tone = "", iconName) => h("span", {class: `chip ${tone}`}, iconName ? icon(iconName) : null, text);
const time = (iso) => h("time", {datetime: iso, text: new Date(iso).toLocaleString([], {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"})});
const fmt = (iso) => new Date(iso).toLocaleString([], {dateStyle: "medium", timeStyle: "short"});

// ---------- state ----------
const app = {
  mode: "real",
  real: {maps: [], observations: [], issues: [], issue_statuses: Object.keys(STATUS_NAMES)},
  wt: null,
  sel: {issueId: null, obsId: null},
  view: "spatial",
  drawer: false,
  media: {}, // observationId -> {url, kind} session-only object URLs, never uploaded
  seen: new Set(), // keys already animated in
  realThread: [],
  copilot: {configured: false, modelId: null},
  boxes: {}, // observationId -> SAM 3.1 result; never persisted
  film: false, // large on-camera captions for recording the walkthrough
};
const data = () => (app.mode === "real" ? app.real : walkthroughData());

function announce(text) { $("#live").textContent = text; }
function toast(text, error = false) {
  const t = $("#toast"); t.textContent = text; t.className = error ? "error" : ""; t.hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => (t.hidden = true), 4200);
  if (!error) announce(text);
}
function fresh(key) { if (app.seen.has(key)) return ""; app.seen.add(key); return " is-new"; }

// ---------- backend adapter (real mode) ----------
async function api(path, body) {
  const options = body ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {};
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw Error(payload.error || "The request failed.");
  return payload;
}
async function refresh() { app.real = await api("/api/state"); render(); }

// ---------- copilot adapter ----------
// Real mode posts to the server's Meta route; the key lives in the server environment, never in this file.
async function requestCopilot({question, selectedIssueId, observationIds}) {
  if (app.mode === "walkthrough") return walkthroughAnswer(question);
  const response = await fetch("/api/copilot", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({question, selectedIssueId, observationIds})});
  const payload = await response.json();
  if (!response.ok) { const error = Error(payload.error || "The copilot request failed."); error.code = payload.code; throw error; }
  return payload;
}
function evidenceForQuestion() { // the selected photo plus up to two most recent others; nothing implicit beyond three
  const obs = [...app.real.observations].sort((a, b) => b.observed_at.localeCompare(a.observed_at));
  const first = obs.find((o) => o.id === app.sel.obsId) || obs[0];
  return first ? [first, ...obs.filter((o) => o !== first).slice(0, 2)].map((o) => o.id) : [];
}

// ---------- scripted walkthrough (fixtures live only in memory) ----------
const WT_SCENE = {id: "wt-scene", kind: "image", localUrl: "#scene-art", mapId: "wt-map", frameId: "courtyard_schematic", registration: "unregistered"};
// screen = position in the schematic's 1200x720 viewBox; placement stays "manual".
const WT_OBS = [
  {id: "wt-o1", title: "Maintenance cart blocking the walkway", observed_at: "2026-10-28T08:12:00-04:00", received_at: "2026-10-28T08:14:31-04:00",
    notes: "Cart parked across the full width of the walkway between Block A and Block B. This walkway is the only step-free route from the blocks to the bus stop.",
    sketch: "cart", via: "Neighbor phone", videoTimeSeconds: 12, anchor: {screen: [700, 390], label: "Cart · Oct 28", tone: ""}},
  {id: "wt-o2", title: "Walkway from Block A (latest view)", observed_at: "2026-11-03T18:40:00-05:00", received_at: "2026-11-03T18:41:02-05:00",
    notes: "Low light. A parked delivery van blocks the line of sight to the cart's last position.",
    sketch: "occluded", via: "Resident phone", anchor: {screen: [430, 520], label: "Nov 3 · occluded", tone: "white"}},
  {id: "wt-o3", title: "Fresh view from the Block B side", observed_at: "2026-11-04T09:52:00-05:00", received_at: "2026-11-04T09:52:40-05:00",
    notes: "Taken from the opposite side, facing the cart's last position. The cart is still on the walkway.",
    sketch: "fresh", via: "Fresh-view request", anchor: {screen: [900, 470], label: "Nov 4 · fresh", tone: "red"}},
];
const BEATS = [ // say: live-region text; film: on-camera caption in film mode
  {key: "capture", label: "Capture", say: "Evidence enters the timeline.", film: "Every view goes into memory, with a time and a place."},
  {key: "map", label: "Enter the map", say: "BenBen's memory of the walkway. The cart anchor links to its source observation.", film: "Oct 28. A cart blocks the only step-free path to the bus."},
  {key: "ask", label: "Ask Muse", say: "Has this path been cleared?", film: "“Has this path been cleared?” The answer comes with receipts."},
  {key: "challenge", label: "Challenge", say: "A resident reports: it is fixed.", film: "“It's fixed.” A claim is not evidence. BenBen asks for one more look."},
  {key: "verify", label: "Verify", say: "A fresh view contradicts the report. The issue stays open.", film: "Still blocked. The issue stays open, and the follow-up writes itself."},
];
const DEFAULT_QUESTION = "Has this path been cleared?";

function startWalkthrough() {
  app.mode = "walkthrough";
  app.wt = {beat: 0, question: null, requested: false, drafted: false, status: "acknowledged"};
  app.sel = {issueId: null, obsId: null}; app.drawer = false; app.view = "spatial";
  document.body.classList.add("wt");
  render(); announce("Scripted walkthrough loaded. Nothing is written to the real workspace.");
}
async function exitWalkthrough() {
  for (const o of WT_OBS) if (app.media[o.id]) { URL.revokeObjectURL(app.media[o.id].url); delete app.media[o.id]; }
  app.mode = "real"; app.wt = null; app.sel = {issueId: null, obsId: null}; app.drawer = false;
  document.body.classList.remove("wt");
  render(); await refresh().catch(() => {}); announce("Back in the real workspace.");
}
function walkthroughData() {
  const {beat} = app.wt;
  const observations = WT_OBS.filter((o) => o.id !== "wt-o3" || beat >= 4).map((o) => ({
    ...o, source: "walkthrough_fixture", timestamp_source: "prepared", map_id: "wt-map", image_url: app.media[o.id]?.kind === "image" ? app.media[o.id].url : null,
  }));
  const issues = beat >= 1 ? [{id: "wt-i1", observation_id: "wt-o1", title: "Walkway blocked by maintenance cart", status: app.wt.status,
    created_at: "2026-10-28T08:20:00-04:00", updated_at: "2026-10-28T08:20:00-04:00"}] : [];
  return {maps: [{id: "wt-map", name: "Bus stop walkway", frame_id: "courtyard_schematic"}], observations, issues, issue_statuses: Object.keys(STATUS_NAMES)};
}
function workflowState() { // frontend evidence state; never posted as an issue status
  if (app.mode !== "walkthrough") return null;
  const {beat, requested} = app.wt;
  if (beat >= 4) return {text: "Contradicted · stays open", tone: "red", icon: "x"};
  if (beat >= 3) return requested ? {text: "View requested", tone: "amber", icon: "cam"} : {text: "Reported fixed · unverified", tone: "", icon: "warn"};
  if (beat >= 2) return {text: "Evidence occluded", tone: "amber", icon: "warn"};
  return null;
}
function walkthroughAnswer(question) {
  return {
    provider: "walkthrough", text: question,
    parts: ["Not confirmed. BenBen's memory has a maintenance cart across the walkway on Oct 28 ", {ref: "wt-o1", t: 12},
      ". The latest view, from Nov 3 ", {ref: "wt-o2"}, ", doesn't show that spot: a parked van blocks the line of sight."],
    evidenceRefs: [{observationId: "wt-o1", videoTimeSeconds: 12}, {observationId: "wt-o2"}], evidenceState: "occluded",
  };
}
function goBeat(index) {
  const wt = app.wt; if (!wt) return;
  wt.beat = Math.max(0, Math.min(BEATS.length - 1, index));
  if (wt.beat < 3) wt.requested = false;
  if (wt.beat < 4) wt.drafted = false;
  if (wt.beat >= 4) wt.requested = true;
  // Each beat focuses the evidence the presenter talks about.
  // Beat 2 waits for the presenter to click the pulsing cart; only the payoff opens the drawer by itself.
  const focus = [null, ["wt-i1", null], ["wt-i1", "wt-o1"], ["wt-i1", "wt-o2"], ["wt-i1", "wt-o3"]][wt.beat];
  app.sel = {issueId: focus ? focus[0] : null, obsId: focus ? focus[1] : null};
  app.drawer = wt.beat === 4;
  render(); announce(`Beat ${wt.beat + 1} of 5, ${BEATS[wt.beat].label}. ${BEATS[wt.beat].say}`);
}

// ---------- selection ----------
function selectObservation(id, {seek} = {}) {
  app.sel.obsId = id; app.drawer = true;
  const issue = data().issues.find((i) => i.observation_id === id);
  if (issue) app.sel.issueId = issue.id;
  if (seek !== undefined && app.media[id]?.kind === "video") app.view = "video";
  render();
  if (seek !== undefined) seekClip(seek);
  const obs = data().observations.find((o) => o.id === id); if (obs) announce(`Selected: ${obs.title}`);
}
function selectIssue(id) {
  const issue = data().issues.find((i) => i.id === id); if (!issue) return;
  app.sel = {issueId: id, obsId: latestFor(issue)?.id || issue.observation_id}; app.drawer = true;
  if (matchMedia("(max-width:1200px)").matches) setOverlay("rail", false);
  render(); announce(`Focused issue: ${issue.title}`);
}
function latestFor(issue) { // newest observation linked to this issue's place; in walkthrough the fresh view counts
  const obs = data().observations;
  if (app.mode === "walkthrough") return obs[obs.length - 1];
  return obs.find((o) => o.id === issue.observation_id);
}
function seekClip(seconds) {
  const video = $("#video-slot video");
  if (video && Number.isFinite(seconds)) { video.currentTime = seconds; video.play().catch(() => {}); }
}

// ---------- rendering ----------
function render() {
  const d = data(), wt = app.mode === "walkthrough";
  $("#mode-pill").textContent = wt ? "Scripted walkthrough" : "Real workspace";
  $("#workspace-name").textContent = wt ? "Bus stop walkway" : "Local workspace";
  $("#walkthrough-toggle").textContent = wt ? "Exit walkthrough" : "Load walkthrough";
  const add = $("#add-observation"); add.disabled = wt; add.title = wt ? "Exit the walkthrough to add real observations." : "";
  $("#frames-section").hidden = wt;
  renderPlace(d); renderIssues(d); renderMaps(d); renderTabs(); renderScene(d); renderVideo(d); renderDrawer(d); renderBeats(); renderStrip(d); renderCopilot(d);
}

function renderPlace(d) {
  const open = d.issues.filter(OPEN).length;
  $("#place-card").replaceChildren(app.mode === "walkthrough"
    ? h("div", {}, h("strong", {text: "Bus stop walkway"}), h("span", {text: `Schematic · ${d.observations.length} observations · ${open} open`}))
    : h("div", {}, h("strong", {text: "Local workspace"}), h("span", {text: `${d.observations.length} observations · ${open} open issues · ${d.maps.length} frames`})));
}

function renderIssues(d) {
  const list = $("#issue-list"); list.replaceChildren();
  const showAll = $("#status-filter").value === "all";
  const issues = d.issues.filter((i) => showAll || OPEN(i));
  if (!issues.length) {
    list.append(h("li", {class: "empty"}, h("strong", {text: d.issues.length ? "Nothing open" : d.observations.length ? "No issues yet" : "Start with an observation"}),
      d.issues.length ? "Switch the filter to see closed issues." : d.observations.length ? "Open an observation and create an issue when something needs follow-up." : "Add a photo of a shared place. Issues grow out of evidence."));
    return;
  }
  const flow = workflowState();
  for (const issue of issues) {
    const select = h("select", {"aria-label": `Status for ${issue.title}`, onchange: () => changeStatus(issue, select)},
      d.issue_statuses.map((s) => h("option", {value: s, text: STATUS_NAMES[s]})));
    select.value = issue.status;
    list.append(h("li", {class: "issue", "aria-current": app.sel.issueId === issue.id ? "true" : "false"},
      h("button", {class: "title", type: "button", text: issue.title, onclick: () => selectIssue(issue.id)}),
      h("div", {class: "meta"}, select, flow ? chip(flow.text, flow.tone, flow.icon) : lastConfirmed(issue))));
  }
}
// "Confirmed clear" only ever comes from a person resolving the issue, never from a model verdict.
function lastConfirmed(issue) {
  const day = (iso) => new Date(iso).toLocaleDateString([], {month: "short", day: "numeric"});
  return issue.status === "resolved" ? chip(`Confirmed clear by a person · ${day(issue.updated_at)}`, "teal", "check")
    : chip(`Open since ${day(issue.created_at)} · not confirmed clear`, OPEN(issue) ? "amber" : "");
}
async function changeStatus(issue, select) {
  if (app.mode === "walkthrough") { app.wt.status = select.value; render(); announce(`Walkthrough issue marked ${STATUS_NAMES[select.value]} (not saved).`); return; }
  select.disabled = true;
  try {
    await api(`/api/issues/${issue.id}/status`, {status: select.value});
    if (!OPEN({status: select.value})) $("#status-filter").value = "all"; // keep the just-closed issue and its confirmation in view
    await refresh(); toast(`Status saved: ${STATUS_NAMES[select.value]}.`);
  }
  catch (error) { select.value = issue.status; select.disabled = false; toast(error.message, true); }
}

function renderMaps(d) {
  $("#map-list").replaceChildren(...(d.maps.length ? d.maps.map((m) => h("li", {text: `${m.name} · ${m.frame_id}`})) : [h("li", {text: "No frames yet."})]));
  const select = $("#observation-map"), current = select.value;
  select.replaceChildren(h("option", {value: "", text: "Location unknown"}), ...d.maps.map((m) => h("option", {value: m.id, text: m.name})));
  if (d.maps.some((m) => m.id === current)) select.value = current;
  updateCoordinateInputs();
}
function updateCoordinateInputs() {
  for (const name of ["x_m", "y_m"]) { const f = document.querySelector(`[name=${name}]`); f.disabled = !$("#observation-map").value; f.required = !f.disabled; }
}

function renderTabs() {
  const spatial = app.view === "spatial";
  $("#tab-spatial").setAttribute("aria-selected", spatial); $("#tab-video").setAttribute("aria-selected", !spatial);
  $("#tab-spatial").tabIndex = spatial ? 0 : -1; $("#tab-video").tabIndex = spatial ? -1 : 0;
  $("#spatial-view").hidden = !spatial; $("#video-view").hidden = spatial;
}

// SceneViewerAdapter: one seam for schematic / image / splat / mesh. Only the schematic is implemented.
const SceneViewerAdapter = {
  supports: (asset) => asset && asset.kind === "image" && asset.localUrl.startsWith("#"),
  mount(container, asset, anchors, {selectedObsId, cones, dim, onSelect}) {
    const art = document.getElementById(asset.localUrl.slice(1)).content.firstElementChild.cloneNode(true);
    art.classList.add("art");
    for (const [id, state] of Object.entries(cones)) {
      const cone = art.querySelector(`#${id}`); if (!cone) continue;
      cone.classList.add("cone"); if (state) cone.classList.add(state);
    }
    container.classList.toggle("dim", dim);
    container.replaceChildren(art, ...anchors.map((a) => {
      const pressed = a.observationId === selectedObsId;
      return h("button", {class: `anchor ${a.tone || ""} ${a.pulse && !pressed ? "pulse" : ""}`, type: "button", "aria-pressed": pressed ? "true" : "false",
        "aria-label": `${a.label}. Placement: ${a.placement}.`, style: `left:${(a.screen[0] / 1200) * 100}%;top:${(a.screen[1] / 720) * 100}%`,
        onclick: () => onSelect(a.observationId)},
      h("span", {class: "dot"}, icon(a.icon)), h("span", {class: "lbl", text: a.label}));
    }));
  },
};

function renderScene(d) {
  const scene = $("#scene"), label = $("#asset-label");
  if (app.mode === "walkthrough") {
    const {beat, requested} = app.wt;
    const anchors = beat < 1 ? [] : d.observations.map((o) => ({id: `a-${o.id}`, observationId: o.id, issueId: o.id === "wt-o1" ? "wt-i1" : undefined, mapId: "wt-map",
      frameId: "courtyard_schematic", placement: "manual", screen: o.anchor.screen, label: o.anchor.label, tone: o.anchor.tone,
      icon: o.id === "wt-o1" ? "warn" : "cam", pulse: o.id === "wt-o1" && beat === 1}));
    const sel = app.sel.obsId;
    SceneViewerAdapter.mount(scene, WT_SCENE, anchors, {
      selectedObsId: sel, dim: beat === 0, onSelect: (id) => selectObservation(id),
      cones: {"cone-before": beat >= 1 && (sel === "wt-o1" || sel === "wt-o2" || beat === 1) ? "on" : "", "cone-fresh": beat >= 4 ? "on" : requested ? "pending" : ""},
    });
    label.textContent = "Schematic scene · unregistered · anchors placed manually";
    return;
  }
  scene.classList.remove("dim");
  const placed = d.observations.filter((o) => o.map_id && Number.isFinite(o.x_m));
  label.textContent = placed.length ? "Manual x/y positions · not a scan" : "No spatial scan loaded";
  if (!placed.length) {
    scene.replaceChildren(h("div", {class: "no-scan view"}, h("div", {},
      h("div", {class: "glyph"}, icon("pin")), h("h3", {text: "No spatial scan loaded"}),
      h("p", {text: "This workspace has no reconstruction. Photos still work: use Add observation. A scan, splat or mesh plugs in through the scene adapter without changing your evidence."}),
      h("button", {class: "ghost", type: "button", text: "See the scripted walkthrough", onclick: startWalkthrough}))));
    return;
  }
  scene.replaceChildren(manualPlot(d, placed));
}
function manualPlot(d, placed) {
  const xs = [0, ...placed.map((p) => p.x_m)], ys = [0, ...placed.map((p) => p.y_m)];
  const minX = Math.min(...xs), minY = Math.min(...ys), span = Math.max(2, Math.max(...xs) - minX, Math.max(...ys) - minY);
  const X = (x) => 120 + ((x - minX) / span) * 820, Y = (y) => 640 - ((y - minY) / span) * 560;
  const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 1200 720"); svg.setAttribute("class", "art plot"); svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Manually entered observation positions; fitted view, no floor plan or robot pose");
  svg.innerHTML = `<line x1="${X(0)}" y1="40" x2="${X(0)}" y2="680" stroke="currentColor" stroke-opacity=".3"/><line x1="60" y1="${Y(0)}" x2="1140" y2="${Y(0)}" stroke="currentColor" stroke-opacity=".3"/><text x="1120" y="${Y(0) - 8}">+x m</text><text x="${X(0) + 8}" y="54">+y m</text>`;
  const scene = h("div", {style: "position:absolute;inset:0"}, svg);
  for (const o of placed) {
    scene.append(h("button", {class: "anchor", type: "button", "aria-pressed": app.sel.obsId === o.id ? "true" : "false", "aria-label": `${o.title}. Manual position ${o.x_m}, ${o.y_m} m.`,
      style: `left:${(X(o.x_m) / 1200) * 100}%;top:${(Y(o.y_m) / 720) * 100}%`, onclick: () => selectObservation(o.id)},
    h("span", {class: "dot"}, icon("pin")), h("span", {class: "lbl", text: `${o.title.slice(0, 24)} · manual`})));
  }
  return scene;
}

function renderVideo(d) {
  const slot = $("#video-slot"), obs = d.observations.find((o) => o.id === app.sel.obsId), clip = obs && app.media[obs.id];
  if (clip?.kind === "video") {
    if (slot.querySelector("video")?.dataset.src === clip.url) return;
    const video = h("video", {src: clip.url, controls: true, playsinline: true, "data-src": clip.url, "aria-label": `Session clip for ${obs.title}`});
    slot.replaceChildren(video, h("p", {}, chip("Session only · not saved", "amber"), " ", obs.videoTimeSeconds !== undefined ? `Cited at 0:${String(obs.videoTimeSeconds).padStart(2, "0")}` : ""));
    return;
  }
  slot.replaceChildren(h("div", {class: "no-scan"}, h("div", {class: "glyph"}, icon("cam")),
    h("h3", {text: obs ? "No clip for this observation" : "No clip loaded"}),
    h("p", {text: "Load a local video to preview it here. It stays in this browser tab and is not uploaded; the backend stores photos only."}),
    mediaPicker(obs ? obs.id : "session", "video/*", "Load local clip")));
}
function mediaPicker(id, accept, label) {
  const input = h("input", {type: "file", accept, class: "sr-only", onchange: () => {
    const file = input.files[0]; if (!file) return;
    if (app.media[id]) URL.revokeObjectURL(app.media[id].url);
    app.media[id] = {url: URL.createObjectURL(file), kind: file.type.startsWith("video") ? "video" : "image"};
    if (app.media[id].kind === "video") app.view = "video";
    render(); toast(`${label}: attached for this session only.`);
  }});
  return h("label", {class: "ghost-label"}, h("span", {class: "chip"}, icon("cam"), label), input);
}

function sketch(kind) { // designed placeholder when no footage exists; labeled as schematic
  const road = `<path d="M10 120 70 46h20l60 74" fill="#0d0f12" stroke="rgba(255,255,255,.35)"/><path d="M80 120V50" stroke="rgba(255,255,255,.12)" stroke-dasharray="3 4"/><path d="M0 30h50v40H0M110 22h50v50h-50" fill="none" stroke="rgba(255,255,255,.18)"/>`;
  const cart = (x, y, s) => `<g transform="translate(${x} ${y}) scale(${s})"><rect x="-16" y="-14" width="32" height="18" rx="2" fill="#15181d" stroke="rgba(255,255,255,.85)"/><rect x="-16" y="-6" width="32" height="3" fill="#f5a524"/><path d="M16 -14l6-8" stroke="rgba(255,255,255,.85)"/><circle cx="-10" cy="7" r="3" fill="none" stroke="rgba(255,255,255,.85)"/><circle cx="10" cy="7" r="3" fill="none" stroke="rgba(255,255,255,.85)"/></g>`;
  const body = {
    cart: road + cart(80, 82, 1.1),
    occluded: road + cart(84, 80, 1) + `<rect x="46" y="52" width="88" height="44" rx="4" fill="#0a0b0d" stroke="rgba(255,255,255,.5)"/><path d="M50 60l20 30M66 56l30 38M86 56l30 38M106 56l24 34" stroke="rgba(255,255,255,.12)"/><text x="90" y="78" text-anchor="middle" fill="rgba(255,255,255,.6)" font-size="8" font-family="ui-monospace,monospace">VAN · OCCLUDED</text>`,
    fresh: `<path d="M150 120 90 46H70l-60 74" fill="#0d0f12" stroke="rgba(255,255,255,.35)"/><path d="M110 30h50v40h-50M0 22h50v50H0" fill="none" stroke="rgba(255,255,255,.18)"/>` + cart(78, 84, 1.25) + `<circle cx="78" cy="78" r="26" fill="none" stroke="#ff6b6b" stroke-dasharray="3 3"/>`,
  }[kind];
  return `<svg viewBox="0 0 160 120" role="img" aria-label="Schematic placeholder, no footage loaded"><rect width="160" height="120" fill="#07080a"/>${body}<text x="6" y="114" fill="rgba(255,255,255,.4)" font-size="6.5" letter-spacing="1" font-family="ui-monospace,monospace">SCHEMATIC · NO FOOTAGE</text></svg>`;
}
function mediaFor(o) {
  const m = app.media[o.id];
  if (o.image_url) return h("img", {src: o.image_url, alt: o.title, loading: "lazy"});
  if (m?.kind === "video") return h("video", {src: m.url, muted: true, playsinline: true, "aria-label": `Session clip: ${o.title}`});
  return h("div", {html: o.sketch ? sketch(o.sketch) : ""});
}

function renderDrawer(d) {
  const drawer = $("#drawer"), obs = d.observations.find((o) => o.id === app.sel.obsId);
  drawer.hidden = !(app.drawer && obs);
  $(".stage").classList.toggle("has-drawer", !drawer.hidden);
  if (drawer.hidden) return;
  const wt = app.mode === "walkthrough", issue = d.issues.find((i) => i.id === app.sel.issueId) || d.issues.find((i) => i.observation_id === obs.id);
  const flow = workflowState(), map = d.maps.find((m) => m.id === obs.map_id);
  const body = [];
  if (issue) body.push(h("p", {class: "kicker"}, `Issue · ${STATUS_NAMES[issue.status]}`),
    h("div", {class: "issue-head"}, h("span", {class: "meta", text: issue.title}), flow ? chip(flow.text, flow.tone, flow.icon) : null));
  body.push(h("h3", {text: obs.title}), h("div", {class: "chips"},
    chip(wt ? "Walkthrough fixture" : "Human upload", wt ? "amber" : "", wt ? "spark" : "cam"),
    map ? chip(wt ? "Manual anchor" : "Manual x/y", "") : chip("Location unknown", "")));
  const before = d.observations.find((o) => o.id === "wt-o1");
  if (wt && app.wt.beat >= 4 && obs.id === "wt-o3" && before) {
    body.push(h("div", {class: "compare"},
      h("figure", {}, h("figcaption", {text: "Before · Oct 28"}), mediaFor(before)),
      h("figure", {class: "now"}, h("figcaption", {text: "Now · Nov 4 · still blocked"}), mediaFor(obs))));
  } else body.push(h("div", {class: "media"}, mediaFor(obs), ...samOverlay(obs)));
  body.push(h("p", {text: obs.notes || "No additional notes."}),
    h("dl", {class: "kv"},
      h("dt", {text: "Observed"}), h("dd", {text: `${fmt(obs.observed_at)} · ${wt ? "prepared" : "entered by contributor"}`}),
      h("dt", {text: "Received"}), h("dd", {text: fmt(obs.received_at)}),
      h("dt", {text: "Source"}), h("dd", {text: wt ? `${obs.via} (scripted)` : "Human upload"}),
      h("dt", {text: "Place"}), h("dd", {text: map ? (wt ? `${map.name} · schematic, unregistered` : `${map.name}: (${obs.x_m}, ${obs.y_m}) m · ${map.frame_id}`) : "Location unknown"}),
      obs.image_sha256 ? [h("dt", {text: "SHA-256"}), h("dd", {text: obs.image_sha256.slice(0, 16) + "…", title: obs.image_sha256})] : null,
      wt && issue ? [h("dt", {text: "Last confirmed clear"}), h("dd", {text: app.wt.beat >= 4 ? "None on record. Blocked Oct 28 and again Nov 4." : "None on record since Oct 28."})] : null,
      !wt && issue ? [h("dt", {text: "Confirmed clear"}), h("dd", {text: issue.status === "resolved" ? `By a person, ${fmt(issue.updated_at)}` : "Not yet. Only a person resolving the issue confirms it."})] : null));
  const actions = h("div", {class: "actions"});
  if (wt) actions.append(mediaPicker(obs.id, "image/*,video/*", "Attach local media"));
  if (!wt && obs.image_url) actions.append(samForm(obs));
  if (!wt && !d.issues.some((i) => i.observation_id === obs.id)) {
    const make = h("button", {type: "button", text: "Create maintenance issue", onclick: async () => {
      make.disabled = true;
      try { const created = await api("/api/issues", {observation_id: obs.id, title: obs.title}); app.sel.issueId = created.id; await refresh(); toast("Maintenance issue created."); }
      catch (error) { make.disabled = false; toast(error.message, true); }
    }});
    actions.append(make);
  }
  body.push(actions);
  $("#drawer-body").replaceChildren(...body);
}

function samOverlay(obs) {
  const result = app.boxes[obs.id]; if (!result) return [];
  return [...result.boxes.map((b) => h("span", {class: "sam-box", style: `left:${b.x * 100}%;top:${b.y * 100}%;width:${b.w * 100}%;height:${b.h * 100}%`},
    h("span", {text: `${result.concept}${b.confidence !== null ? ` ${Math.round(b.confidence * 100)}%` : ""}`}))),
  h("span", {class: "sam-tag"}, chip(`SAM 3.1 · ${result.boxes.length} found · ${result.latencyMs} ms`, result.boxes.length ? "red" : "teal"))];
}
function samForm(obs) {
  const input = h("input", {value: app.boxes[obs.id]?.concept || "cart", maxlength: "40", "aria-label": "What to mark in this photo"});
  const button = h("button", {type: "submit", class: "ghost"}, "Mark with SAM 3.1");
  return h("form", {class: "sam-form", onsubmit: async (event) => {
    event.preventDefault(); button.disabled = true;
    try {
      const response = await fetch("/api/segment", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({observationId: obs.id, concept: input.value})});
      const payload = await response.json();
      if (!response.ok) throw Error(payload.error || "Segmentation failed.");
      app.boxes[obs.id] = payload; render(); announce(`SAM found ${payload.boxes.length} ${payload.concept}.`);
    } catch (error) { toast(error.message, true); } finally { button.disabled = false; }
  }}, input, button);
}

function renderBeats() {
  const bar = $("#beats"); bar.hidden = app.mode !== "walkthrough";
  const film = !bar.hidden && app.film;
  document.body.classList.toggle("film", film);
  $("#film-toggle").hidden = bar.hidden; $("#film-toggle").setAttribute("aria-pressed", String(film));
  $("#caption").hidden = $("#film-bug").hidden = !film;
  if (bar.hidden) return;
  const {beat} = app.wt;
  if (film && $("#caption-text").textContent !== BEATS[beat].film) {
    $("#caption-kicker").textContent = `${beat + 1} / 5 · ${BEATS[beat].label}`;
    $("#caption-text").textContent = BEATS[beat].film;
    $("#caption").classList.remove("is-new"); void $("#caption").offsetWidth; $("#caption").classList.add("is-new");
  }
  $("#beat-list").replaceChildren(...BEATS.map((b, i) => h("li", {}, h("button", {type: "button", class: i < beat ? "done" : "", "aria-current": i === beat ? "step" : "false",
    "aria-label": `${i + 1}. ${b.label}`, onclick: () => goBeat(i)}, i === beat ? `${i + 1} · ${b.label}` : `${i + 1}`))));
  $("#beat-prev").disabled = beat === 0;
  const next = $("#beat-next"); next.disabled = beat === BEATS.length - 1;
  next.textContent = beat === 2 ? "Challenge →" : beat === 3 ? "Fresh view →" : "Next beat →";
}

function renderStrip(d) {
  const strip = $("#strip"), obs = [...d.observations].sort((a, b) => a.observed_at.localeCompare(b.observed_at));
  $("#strip-count").textContent = `${obs.length} observation${obs.length === 1 ? "" : "s"}`;
  if (!obs.length) {
    strip.replaceChildren(h("div", {class: "empty", style: "flex:1"}, h("strong", {text: "No observations yet"}),
      app.mode === "real" ? "Use Add observation to save a photo. Your evidence appears here in the order it was observed." : ""));
    return;
  }
  strip.replaceChildren(...obs.map((o) => h("button", {class: `ev${fresh("ev" + o.id)}`, type: "button", "aria-pressed": app.sel.obsId === o.id ? "true" : "false",
    onclick: () => selectObservation(o.id, {seek: o.videoTimeSeconds})},
  h("span", {class: "thumb"}, mediaFor(o)),
  h("span", {}, h("strong", {text: o.title}), time(o.observed_at),
    app.mode === "walkthrough" ? chip(o.via, o.id === "wt-o3" ? "red" : "", "cam") : chip("Human upload", "", "cam")))));
}

function citeButton(ref) {
  const o = data().observations.find((x) => x.id === ref.ref);
  if (!o) return h("span", {class: "chip", text: "missing source"});
  const stamp = new Date(o.observed_at).toLocaleDateString([], {month: "short", day: "numeric"});
  return h("button", {class: "cite", type: "button", onclick: () => selectObservation(o.id, {seek: ref.t}), "aria-label": `Open source observation: ${o.title}`},
    `▸ ${stamp}${ref.t !== undefined ? ` · 0:${String(ref.t).padStart(2, "0")}` : ""}`);
}
const VERDICT_CHIP = {supported: ["Supports the claim", "teal", "check"], contradicted: ["Contradicts the claim", "red", "x"], insufficient: ["Can't tell yet", "amber", "warn"]};
const STATE_CHIP = {sufficient: ["Evidence sufficient", "teal", "check"], stale: ["Evidence stale", "amber", "warn"], occluded: ["Evidence occluded", "amber", "warn"], missing: ["Evidence missing", "amber", "warn"]};

function renderCopilot(d) {
  const thread = $("#thread"), wt = app.mode === "walkthrough", items = [];
  const live = app.copilot.configured;
  const via = app.copilot.provider === "baseten" ? "open weights via Baseten" : "Meta Model API";
  $("#provider-label").textContent = wt ? "Prepared walkthrough text" : live ? `${via} · ${app.copilot.modelId}` : "Not connected";
  if (!wt) {
    items.push(h("div", {class: "msg"}, h("div", {class: "who"}, speaker("Muse", live ? "connected" : "not connected")),
      h("p", {text: live ? "Ask about this place's history. Muse answers from your photos and cites them; select a citation to open its evidence."
        : "Ask about this place's history once a key is set in the server's environment (MODEL_API_KEY, or BASETEN_API_KEY with META_PROVIDER=baseten) and the server restarts."}),
      h("p", {class: "muted", text: live ? `Asking sends the selected photo and up to two recent ones, with their titles, notes and times, to ${app.copilot.provider === "baseten" ? "Baseten (Muse Spark Open)" : "Meta's API"}. Answers never change an issue's status.`
        : "Nothing here is simulated: until a provider is configured, questions return this notice."})));
    for (const m of app.realThread) items.push(m);
  } else {
    const {beat, requested, drafted} = app.wt;
    if (beat < 2) items.push(h("div", {class: "msg" + fresh("m-intro")}, h("div", {class: "who"}, speaker("BenBen", "walkthrough")),
      h("p", {text: beat === 0 ? "BenBen used to count pallets in a warehouse. Now he keeps watch over the estate's walk to the bus: every view, with a time and a place." : "Select the cart anchor, or ask a question about the walkway."})));
    if (beat >= 2) {
      const answer = walkthroughAnswer(app.wt.question || DEFAULT_QUESTION);
      items.push(h("div", {class: "msg user" + fresh("m-q")}, h("p", {text: answer.text})));
      items.push(h("div", {class: "msg answer" + fresh("m-a")}, h("div", {class: "who"}, speaker("Muse", "prepared"), chip(...STATE_CHIP[answer.evidenceState])),
        h("p", {}, answer.parts.map((p) => (typeof p === "string" ? p : citeButton(p))))));
    }
    if (beat >= 3) {
      items.push(h("div", {class: "msg claim" + fresh("m-claim")}, h("div", {class: "who"}, speaker("Resident report", "Nov 4, 9:40"), chip("Claim, unverified", "", "warn")),
        h("p", {class: "lead", text: "“It's fixed.”"})));
      items.push(h("div", {class: "msg gap" + fresh("m-gap")}, h("div", {class: "who"}, speaker("Muse", "prepared"), chip(...STATE_CHIP.occluded), chip(...VERDICT_CHIP.insufficient)),
        h("p", {}, "Logged as a claim, not a resolution. The newest view ", citeButton({ref: "wt-o2"}), " can't see the spot, so the issue stays open until someone looks."),
        !requested ? h("div", {class: "actions"}, h("button", {type: "button", onclick: requestView}, icon("cam"), "Request a fresh view")) : null));
    }
    if (requested) {
      items.push(h("div", {class: "msg request" + fresh("m-req")}, h("div", {class: "who"}, chip(beat >= 4 ? "View request · fulfilled" : "View request · pending", beat >= 4 ? "teal" : "amber", beat >= 4 ? "check" : "cam")),
        h("p", {text: "Wanted: one photo from the Block B side, facing the cart's last position. A phone photo counts. No robot command was sent."}),
        beat === 3 ? h("div", {class: "actions"}, h("button", {type: "button", onclick: () => goBeat(4)}, "Use prepared fresh view"), mediaPicker("wt-o3", "image/*,video/*", "Attach a photo")) : null));
    }
    if (beat >= 4) {
      items.push(h("div", {class: "msg verdict" + fresh("m-verdict")}, h("div", {class: "who"}, speaker("Muse", "prepared"), chip("Contradicts the claim", "red", "x"), chip(...STATE_CHIP.sufficient)),
        h("p", {class: "lead", text: "The cart is still on the walkway."}),
        h("p", {}, "Fresh view ", citeButton({ref: "wt-o3"}), " matches the Oct 28 observation ", citeButton({ref: "wt-o1", t: 12}), ". The report doesn't hold. Issue stays ", h("strong", {text: STATUS_NAMES[app.wt.status]}), "."),
        !drafted ? h("div", {class: "actions"}, h("button", {type: "button", onclick: () => { app.wt.drafted = true; render(); announce("Follow-up drafted. Not sent."); }}, "Draft follow-up")) : null));
    }
    if (drafted) {
      items.push(h("div", {class: "msg handover" + fresh("m-hand")}, h("div", {class: "who"}, chip("Next action · draft, not sent", "teal", "check")),
        h("pre", {text: "To: Estate facilities\nRe: Walkway still blocked by maintenance cart\n\nReported fixed Nov 4, 9:40 (resident).\nFresh view Nov 4, 9:52: the cart is still on the walkway.\nEvidence: Oct 28 8:12 · Nov 4 9:52\n\nPlease move the cart off the walkway and reply\nwith a photo once it's clear."}),
        h("p", {class: "stamp", text: "BENBEN HAS THE RECEIPTS"})));
    }
  }
  thread.replaceChildren(...items);
  thread.scrollTop = thread.scrollHeight;
  $("#mic").hidden = wt;
  $("#ask-input").placeholder = wt && app.wt.beat < 2 ? DEFAULT_QUESTION : "Ask about this place's history…";
  // Astra: prepared second-reviewer text, shown only inside the labeled walkthrough; no unwired AI panel in real mode.
  $("#astra").hidden = !wt;
  const astra = !wt ? ["Not connected", "No second reviewer has run on this workspace."]
    : app.wt.beat >= 4 ? ["Prepared · agrees", "Agrees with Muse: the fresh view covers the cart's position, and it contradicts the report."]
      : app.wt.beat >= 3 ? ["Prepared · flags gap", "The Nov 3 view is occluded where the cart was. A view from the opposite side would settle it."]
        : ["Prepared · idle", "Reviews evidence gaps once a claim needs checking."];
  $("#astra-state").textContent = astra[0];
  $("#astra-body").replaceChildren(h("p", {text: astra[1]}));
}
function requestView() { app.wt.requested = true; render(); announce("Fresh view requested. Pending. No robot command was sent."); }

// ---------- events ----------
async function ask(event) {
  event.preventDefault();
  const input = $("#ask-input"), question = input.value.trim() || (app.mode === "walkthrough" ? DEFAULT_QUESTION : "");
  if (!question) return;
  input.value = "";
  if (app.mode === "walkthrough") { app.wt.question = question; if (app.wt.beat < 2) goBeat(2); else render(); return; }
  const observationIds = evidenceForQuestion();
  app.realThread.push(h("div", {class: "msg user"}, h("p", {text: question})));
  if (!observationIds.length) {
    app.realThread.push(h("div", {class: "msg gap"}, h("div", {class: "who"}, chip(...STATE_CHIP.missing)), h("p", {text: "Add a photo first. Muse only answers from evidence in this workspace."})));
    render(); return;
  }
  const pending = h("div", {class: "msg"}, h("div", {class: "who"}, speaker("Muse", "asking…")), h("p", {class: "muted", text: `Sending ${observationIds.length} photo${observationIds.length === 1 ? "" : "s"}…`}));
  app.realThread.push(pending); render();
  const submit = $("#ask-form button[type=submit]"); submit.disabled = true;
  try {
    const answer = await requestCopilot({question, selectedIssueId: app.sel.issueId, observationIds});
    app.realThread[app.realThread.indexOf(pending)] = h("div", {class: "msg answer is-new"},
      h("div", {class: "who"}, speaker("Muse", `live · ${answer.modelId}${answer.provider === "baseten" ? " via Baseten" : ""} · ${answer.latencyMs} ms`), chip(...STATE_CHIP[answer.evidenceState])),
      VERDICT_CHIP[answer.claimVerdict] ? h("p", {}, chip(...VERDICT_CHIP[answer.claimVerdict])) : null,
      h("p", {text: answer.text}),
      h("p", {}, answer.evidenceRefs.map((r) => citeButton({ref: r.observationId}))),
      answer.proposedAction === "request_view" ? h("div", {class: "actions"}, h("button", {type: "button", onclick: (e) => requestRealView(e.currentTarget)}, icon("cam"), "Request a fresh view")) : null);
    announce("Muse answered.");
  } catch (error) {
    app.realThread[app.realThread.indexOf(pending)] = h("div", {class: "msg gap is-new"},
      h("div", {class: "who"}, chip(error.code === "unconfigured" ? "No provider connected" : "Muse request failed", "amber", "warn")),
      h("p", {text: error.code === "unconfigured" ? "Set MODEL_API_KEY in the server's environment and restart it. Nothing was sent." : error.message}));
    announce(error.message);
  } finally { submit.disabled = false; render(); }
}
// Voice: record up to 10 s of 16 kHz mono PCM, encode WAV here (Meta's ASR wants WAV), transcribe server-side.
function encodeWav(chunks, rate) {
  const n = chunks.reduce((sum, c) => sum + c.length, 0), view = new DataView(new ArrayBuffer(44 + n * 2));
  const tag = (offset, text) => [...text].forEach((ch, i) => view.setUint8(offset + i, ch.charCodeAt(0)));
  tag(0, "RIFF"); view.setUint32(4, 36 + n * 2, true); tag(8, "WAVE"); tag(12, "fmt "); view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); tag(36, "data"); view.setUint32(40, n * 2, true);
  let offset = 44;
  for (const chunk of chunks) for (const sample of chunk) { view.setInt16(offset, Math.max(-1, Math.min(1, sample)) * 0x7fff, true); offset += 2; }
  return new Uint8Array(view.buffer);
}
function toBase64(bytes) { let s = ""; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000)); return btoa(s); }
async function recordClaim() {
  const mic = $("#mic");
  if (app.recording) return app.recording();
  if (mic.dataset.starting) return; // second click while the permission prompt is open
  mic.dataset.starting = "1";
  let stream, ctx, source, node;
  const chunks = [];
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: true});
    ctx = new AudioContext({sampleRate: 16000}); source = ctx.createMediaStreamSource(stream); node = ctx.createScriptProcessor(4096, 1, 1);
  } catch {
    stream?.getTracks().forEach((t) => t.stop()); ctx?.close();
    toast("Could not start the microphone in this browser.", true); return;
  } finally { delete mic.dataset.starting; }
  node.onaudioprocess = (e) => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
  source.connect(node); node.connect(ctx.destination);
  mic.setAttribute("aria-pressed", "true"); mic.textContent = "■"; announce("Recording. Press again to stop.");
  const timer = setTimeout(() => app.recording && app.recording(), 10000);
  app.recording = async () => {
    clearTimeout(timer); app.recording = null; node.disconnect(); source.disconnect(); stream.getTracks().forEach((t) => t.stop());
    const rate = ctx.sampleRate; await ctx.close();
    mic.setAttribute("aria-pressed", "false"); mic.textContent = "🎙"; mic.disabled = true;
    try {
      const response = await fetch("/api/transcribe", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({audio_wav_base64: toBase64(encodeWav(chunks, rate))})});
      const payload = await response.json();
      if (!response.ok) throw Error(payload.code === "unconfigured" ? "Set MODEL_API_KEY on the server to transcribe. Nothing was sent." : payload.error);
      app.realThread.push(h("div", {class: "msg claim is-new"}, h("div", {class: "who"}, speaker("Spoken claim", `${payload.modelId} · ${payload.latencyMs} ms`), chip("Claim, unverified", "", "warn")),
        h("p", {class: "lead", text: `“${payload.text}”`})));
      $("#ask-input").value = `Someone says: "${payload.text.slice(0, 400)}" Do the photos support that?`;
      render(); $("#ask-input").focus(); announce(`Heard: ${payload.text}`);
    } catch (error) { toast(error.message, true); } finally { mic.disabled = false; }
  };
}

function requestRealView(button) { // local UI state only: no robot command, no remote job
  button.remove();
  app.realThread.push(h("div", {class: "msg request is-new"}, h("div", {class: "who"}, chip("View request · pending", "amber", "cam")),
    h("p", {text: "Wanted: one new photo of the same spot, from an angle that shows it clearly. A phone photo counts. No robot command was sent."}),
    h("div", {class: "actions"}, h("button", {type: "button", onclick: () => $("#observation-dialog").showModal()}, "Add the fresh photo"))));
  render(); announce("Fresh view requested. Add a photo to fulfill it.");
}
function setOverlay(which, open) {
  document.body.classList.toggle(`${which}-open`, open);
  $(`#toggle-${which}`).setAttribute("aria-expanded", String(open));
}
function localInputNow() { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }

async function saveObservation(event) {
  event.preventDefault();
  const form = event.currentTarget, button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const file = $("#image").files[0];
    if (!file) throw Error("Choose an evidence photo.");
    if (file.size > 5 * 1024 * 1024) throw Error("Choose a photo smaller than 5 MiB.");
    const image = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1]);
      reader.onerror = () => reject(Error("Could not read the image."));
      reader.readAsDataURL(file);
    });
    const values = new FormData(form);
    const body = {title: values.get("title"), notes: values.get("notes"), observed_at: new Date(values.get("observed_at")).toISOString(), image_base64: image};
    if (values.get("map_id")) Object.assign(body, {map_id: values.get("map_id"), x_m: Number(values.get("x_m")), y_m: Number(values.get("y_m"))});
    const created = await api("/api/observations", body);
    form.reset(); $("#observed-at").value = localInputNow(); $("#observation-dialog").close();
    app.sel = {issueId: null, obsId: created.id}; app.drawer = true;
    await refresh(); toast("Observation saved. Create an issue from its detail panel.");
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
}

$("#observed-at").value = localInputNow();
$("#observation-form").addEventListener("submit", saveObservation);
$("#add-observation").addEventListener("click", () => $("#observation-dialog").showModal());
$("#cancel-observation").addEventListener("click", () => $("#observation-dialog").close());
$("#map-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget, button = form.querySelector("button"); button.disabled = true;
  try { const v = new FormData(form); await api("/api/maps", {name: v.get("name"), frame_id: v.get("frame_id")}); form.reset(); await refresh(); toast("Coordinate frame added."); }
  catch (error) { toast(error.message, true); } finally { button.disabled = false; }
});
$("#observation-map").addEventListener("change", updateCoordinateInputs);
$("#status-filter").addEventListener("change", () => renderIssues(data()));
$("#walkthrough-toggle").addEventListener("click", () => (app.mode === "walkthrough" ? exitWalkthrough() : startWalkthrough()));
$("#film-toggle").addEventListener("click", () => { app.film = !app.film; renderBeats(); });
$("#beat-next").addEventListener("click", () => goBeat(app.wt.beat + 1));
$("#beat-prev").addEventListener("click", () => goBeat(app.wt.beat - 1));
$("#close-drawer").addEventListener("click", () => { app.drawer = false; render(); });
$("#ask-form").addEventListener("submit", ask);
$("#mic").addEventListener("click", recordClaim);
for (const [tab, view] of [["#tab-spatial", "spatial"], ["#tab-video", "video"]]) $(tab).addEventListener("click", () => { app.view = view; renderTabs(); });
$(".tabs").addEventListener("keydown", (e) => { if (["ArrowLeft", "ArrowRight"].includes(e.key)) { app.view = app.view === "spatial" ? "video" : "spatial"; renderTabs(); $(app.view === "spatial" ? "#tab-spatial" : "#tab-video").focus(); } });
$("#toggle-rail").addEventListener("click", () => setOverlay("rail", !document.body.classList.contains("rail-open")));
$("#toggle-copilot").addEventListener("click", () => setOverlay("copilot", !document.body.classList.contains("copilot-open")));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { if (app.drawer) { app.drawer = false; render(); } setOverlay("rail", false); setOverlay("copilot", false); return; }
  if (app.mode !== "walkthrough" || e.target.closest?.("input,textarea,select,[role=tab]") || e.metaKey || e.ctrlKey) return;
  if (e.key === "f" || e.key === "F") { app.film = !app.film; renderBeats(); announce(app.film ? "Film mode on." : "Film mode off."); return; }
  if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); goBeat(app.wt.beat + 1); }
  if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); goBeat(app.wt.beat - 1); }
});
if (new URLSearchParams(location.search).get("theme") === "dark") document.documentElement.dataset.theme = "dark";
if (new URLSearchParams(location.search).has("walkthrough")) startWalkthrough();
refresh().catch((error) => toast(`Could not load the workspace: ${error.message}`, true));
fetch("/api/copilot/status").then((r) => r.json()).then((s) => { app.copilot = s; render(); }).catch(() => {});
