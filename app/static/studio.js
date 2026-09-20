/* Preeti Studio — shot-level production workspace (vanilla JS, no build step). */
(() => {
  const API = "/api/v1";
  const $ = (sel, root = document) => root.querySelector(sel);
  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "style") node.style.cssText = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else if (k === "html") node.innerHTML = v;
      else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat()) {
      if (c === null || c === undefined || c === false) continue;
      node.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return node;
  };
  const stream = (path) => `${API}/media/stream?path=${encodeURIComponent(path)}`;
  const fmtTime = (iso) => iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // ---------------------------------------------------------------- API
  async function api(method, path, body, opts = {}) {
    const init = { method, headers: {} };
    if (body instanceof FormData) init.body = body;
    else if (body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    const res = await fetch(API + path, init);
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || j); } catch {}
      if (!opts.silent) toast(detail, "err");
      throw new Error(detail);
    }
    return res.status === 204 ? null : res.json();
  }
  const get = (p, o) => api("GET", p, undefined, o);
  const post = (p, b, o) => api("POST", p, b ?? {}, o);
  const patch = (p, b) => api("PATCH", p, b);
  const del = (p, b) => api("DELETE", p, b);

  // ---------------------------------------------------------------- UI helpers
  function toast(msg, kind = "") {
    const t = el("div", { class: `toast ${kind}` }, msg);
    $("#toasts").append(t);
    setTimeout(() => t.remove(), kind === "err" ? 7000 : 3500);
  }
  function modal(title, body, { wide = false, lightbox = false } = {}) {
    const root = $("#modal-root");
    const close = () => root.replaceChildren();
    const box = el("div", { class: `modal ${lightbox ? "lightbox" : ""}`, style: wide ? "width:min(1200px,94vw)" : "" });
    if (!lightbox) box.append(el("div", { class: "modal-h" }, el("h3", {}, title), el("button", { class: "btn ghost sm", onclick: close }, "✕")));
    box.append(lightbox ? body : el("div", { class: "modal-b" }, body));
    const bg = el("div", { class: "modal-bg", onclick: (e) => { if (e.target === bg) close(); } }, box);
    root.replaceChildren(bg);
    document.addEventListener("keydown", function esc(e) { if (e.key === "Escape") { close(); document.removeEventListener("keydown", esc); } });
    return close;
  }
  const lightbox = (src, isVideo) => modal("", isVideo ? el("video", { src, controls: true, autoplay: true }) : el("img", { src }), { lightbox: true });
  function confirmDlg(text) { return Promise.resolve(window.confirm(text)); }
  function field(label, input, hint) {
    return el("div", { class: "field" }, el("label", { class: "f" }, label), input, hint ? el("div", { class: "hint" }, hint) : null);
  }
  function select(options, value, onchange, attrs = {}) {
    const s = el("select", { ...attrs, onchange: (e) => onchange && onchange(e.target.value) });
    for (const o of options) {
      const [v, label, disabled] = Array.isArray(o) ? o : [o, o, false];
      s.append(el("option", { value: v, disabled: disabled || null, selected: String(v) === String(value) || null }, label));
    }
    return s;
  }
  const badge = (text, kind = "") => el("span", { class: `badge ${kind}` }, text);
  const statusKind = (s) => ({ SUCCEEDED: "ok", RUNNING: "accent", PENDING: "info", FAILED_FINAL: "err", FAILED_RETRYABLE: "warn", CANCELLED: "" }[s] || "");

  // ---------------------------------------------------------------- Global state & polling
  const state = { engines: null, caps: null, jobs: [], progress: {}, activeBoard: null, activeShot: null, seenEvents: {} };
  let dockOpen = false;

  async function pollGlobal() {
    try {
      const [jobs, prog] = await Promise.all([get("/jobs?limit=60", { silent: true }), get("/creator/progress/__none__", { silent: true })]);
      state.jobs = jobs.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
      const sys = prog.system || {};
      const gpu = sys.gpu || {};
      $("#sys-gpu").textContent = gpu.error ? "GPU unavailable" : `GPU ${gpu.utilization_percent}% · ${Math.round(gpu.vram_used_mib / 1024 * 10) / 10}/${Math.round(gpu.vram_total_mib / 1024)} GB`;
      const running = state.jobs.filter((j) => j.status === "RUNNING").length;
      const pending = state.jobs.filter((j) => j.status === "PENDING").length;
      $("#sys-queue").textContent = `Queue ${running} running · ${pending} waiting · Comfy ${sys.comfy?.online ? "online" : "offline"}`;
      $("#sys-status").textContent = `RAM ${sys.ram_percent}% · CPU ${sys.cpu_percent}%`;
      $("#dock-title").textContent = running ? `Jobs · ${running} running, ${pending} queued` : pending ? `Jobs · ${pending} queued` : "Jobs";
      renderDock();
      // Pull live progress for running jobs
      for (const j of state.jobs.filter((j) => j.status === "RUNNING")) {
        try {
          const s = await get(`/storyboards/jobs/${j.id}`, { silent: true });
          state.progress[j.id] = s.progress;
          const seen = state.seenEvents[j.id] || 0;
          for (const ev of (s.progress.events || []).slice(seen)) consoleLine(`[${new Date(ev.time).toLocaleTimeString()}] ${ev.stage}: ${ev.message}`, ev.level);
          state.seenEvents[j.id] = (s.progress.events || []).length;
        } catch {}
      }
      if (state.activeBoard && (running || pending || state._hadActivity)) {
        state._hadActivity = !!(running || pending);
        await refreshBoard();
      }
    } catch (e) { $("#sys-status").textContent = "Studio Core offline"; }
  }
  function consoleLine(text, level = "info") {
    const c = $("#dock-console");
    const line = el("div", { class: level === "error" ? "err" : level === "warning" ? "warn" : "" }, text);
    c.append(line);
    while (c.children.length > 400) c.firstChild.remove();
    c.scrollTop = c.scrollHeight;
  }
  function renderDock() {
    const box = $("#dock-jobs");
    box.replaceChildren(...state.jobs.slice(0, 40).map((j) => {
      const p = state.progress[j.id];
      const label = `${j.kind.replace("_", " ")}${j.payload_json?.shot_id ? "" : ""}`;
      return el("div", { class: "dock-job" },
        el("div", {}, el("div", {}, label, " ", badge(j.status.replace("_", " ").toLowerCase(), statusKind(j.status))),
          el("div", { class: "k small" }, p && j.status === "RUNNING" ? `${p.stage} · ${p.progress}% · ${Math.round(p.elapsed_s)}s` : j.error_message ? j.error_message.split("\n")[0].slice(0, 90) : fmtTime(j.created_at))),
        j.status === "PENDING" || j.status === "RUNNING" ? el("button", { class: "btn xs", onclick: () => post(`/storyboards/jobs/${j.id}/cancel`).then(pollGlobal) }, "cancel") : null);
    }));
  }
  $("#dock-toggle").addEventListener("click", () => { dockOpen = !dockOpen; $("#jobs-dock").classList.toggle("collapsed", !dockOpen); });

  async function loadEngines() {
    const all = await get("/storyboards/engines", { silent: true }).catch(() => null);
    state.engines = all?.motion || null;
    state.voiceEngines = all?.voice || {};
    state.musicEngines = all?.music || {};
    state.caps = await get("/capabilities", { silent: true }).catch(() => null);
  }
  const engineOptions = (map, current) => Object.entries(map || {}).map(([k, e]) => [k, `${e.label}${e.available ? "" : " — unavailable"}`, !e.available && k !== current]);

  // ---------------------------------------------------------------- Router
  const routes = {};
  function navigate() {
    const hash = location.hash.replace(/^#\/?/, "") || "home";
    const [name, ...rest] = hash.split("/");
    const route = routes[name] || routes.home;
    document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.route === name));
    state.activeBoard = null;
    const view = $("#view");
    view.replaceChildren(el("div", { class: "page muted" }, "Loading…"));
    Promise.resolve(route(rest)).then((node) => { if (node) view.replaceChildren(node); }).catch((e) => view.replaceChildren(el("div", { class: "page" }, el("div", { class: "empty-state" }, String(e.message || e)))));
  }
  window.addEventListener("hashchange", navigate);

  // ---------------------------------------------------------------- Home
  routes.home = async () => {
    const { storyboards } = await get("/storyboards");
    const caps = state.caps || (await get("/capabilities"));
    const sum = caps.summary;
    const page = el("div", { class: "page" },
      el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "Your videos"), el("p", {}, "Every video is a storyboard of shots you can edit, regenerate and re-assemble.")),
        el("a", { class: "btn primary", href: "#/new" }, "＋ New video")),
      el("div", { class: "grid cols-4", style: "margin-bottom:22px" },
        el("div", { class: "card stat" }, el("div", { class: "v" }, storyboards.length), el("div", { class: "l" }, "storyboards")),
        el("div", { class: "card stat" }, el("div", { class: "v" }, sum.verified_engines), el("div", { class: "l" }, "verified engines")),
        el("div", { class: "card stat" }, el("div", { class: "v" }, sum.blocked_engines), el("div", { class: "l" }, "installed, not yet verified")),
        el("div", { class: "card stat" }, el("div", { class: "v" }, `${sum.free_disk_gib} GB`), el("div", { class: "l" }, "free disk"))),
    );
    if (!storyboards.length) page.append(el("div", { class: "card empty-state" }, "No videos yet. Create one from a script — you'll get an editable shot list before anything renders."));
    else page.append(el("div", { class: "grid cols-4" }, ...storyboards.map((b) => {
      const thumb = b.latest_render?.thumbnails?.[0];
      return el("a", { class: "thumb-card", href: `#/board/${b.id}` },
        thumb ? el("img", { src: stream(thumb), loading: "lazy" }) : el("div", { style: "aspect-ratio:9/16;display:grid;place-items:center;color:var(--text-3);font-size:32px" }, "🎬"),
        el("span", { class: `badge tag ${b.status === "RENDERED" ? "ok" : ""}` }, b.status.toLowerCase()),
        el("div", { class: "cap" }, el("div", { class: "t" }, b.title), el("div", { class: "m" }, `${b.shot_count} shots · ${b.settings.aspect_ratio} · ${fmtTime(b.updated_at)}`)));
    })));
    return page;
  };

  // ---------------------------------------------------------------- New video
  const PRESETS = {
    cyberpunk: ["The Neon Cipher", `SCENE 1: EXT. NEO-MUMBAI RAINY STREET - NIGHT\nNeon signs reflect off the wet pavement. Diya (24), wearing a dark high-collar coat, walks quickly down the alley, checking her holographic wrist display.\n\nDIYA\n(whispering urgently)\nThe transmission is locked. We have under a minute before they trace the signal.`],
    romance: ["Monsoon Coffee", `SCENE 1: INT. COZY MONSOON CAFE - EVENING\nRain patters against the warm amber glass. Priya sits with a steaming cup of tea, sketching in her journal.\nAarav pauses by the doorway, his umbrella dripping, catching her eye with a warm smile.\n\nPRIYA\n(smiling softly)\nYou're ten minutes late. But I ordered your favorite.`],
    mystery: ["The Basement Archive", `SCENE 1: INT. ARCHIVE BASEMENT - NIGHT\nDust motes float through a single shaft of moonlight. Kabir uncovers a locked wooden safe behind the bookshelf.\nHe turns the antique brass dial until it clicks open.\n\nKABIR\n(holding up the ledger)\nIt's all here. The accounts were never destroyed.`],
    scifi: ["The Deep Signal", `SCENE 1: INT. ORBITAL OBSERVATORY - CONTINUOUS\nStarlight floods the observation deck. Commander Tara watches an anomaly pulsing on the deep space telemetry screen.\n\nTARA\n(into communications badge)\nStation Control, this isn't random radiation. It's an intelligent sequence.`],
  };
  routes.new = async () => {
    const form = { title: "The Neon Cipher", script: PRESETS.cyberpunk[1], duration: 20, settings: { aspect_ratio: "9:16", genre: "cyberpunk_thriller", quality_profile: "balanced", seed: 42, style_prompt: "", keyframe_candidates: 2, music_engine: "off", foley_engine: "library", burn_subtitles: true, frame_interpolation: "off" } };
    const title = el("input", { type: "text", value: form.title, oninput: (e) => (form.title = e.target.value) });
    const script = el("textarea", { style: "min-height:220px", oninput: (e) => (form.script = e.target.value) }, form.script);
    const chips = el("div", { class: "chips" }, ...Object.entries(PRESETS).map(([k, [t, s]]) => el("button", { class: "chip", onclick: () => { title.value = form.title = t; script.value = form.script = s; } }, t)));
    const setS = (k) => (v) => (form.settings[k] = v);
    const page = el("div", { class: "page" },
      el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "New video"), el("p", {}, "Write or paste a script. Nothing renders until you review the shot list."))),
      el("div", { style: "display:grid;grid-template-columns:1.4fr 1fr;gap:18px" },
        el("div", { class: "card card-pad" },
          field("Title", title), field("Story ideas", chips), field("Script / dialogue / action", script, "Use SCENE headings and NAME lines for dialogue. Each dialogue line becomes its own shot.")),
        el("div", { class: "card card-pad" },
          el("div", { class: "two" },
            field("Aspect", select([["9:16", "9:16 Portrait"], ["16:9", "16:9 Landscape"], ["1:1", "1:1 Square"]], "9:16", setS("aspect_ratio"))),
            field("Target length", select([[10, "10 s"], [15, "15 s"], [20, "20 s"], [30, "30 s"], [45, "45 s"], [60, "60 s"]], 20, (v) => (form.duration = Number(v))))),
          el("div", { class: "two" },
            field("Genre / look", select([["cyberpunk_thriller", "Cyberpunk thriller"], ["suspense_drama", "Suspense drama"], ["romance_cinematic", "Romantic cinematic"], ["action_chase", "Action"]], "cyberpunk_thriller", setS("genre"))),
            field("Quality", select([["draft", "Draft (fast)"], ["balanced", "Balanced"], ["quality", "Quality (slow)"]], "balanced", setS("quality_profile")))),
          field("Style prompt (appended to every keyframe)", el("input", { type: "text", placeholder: "e.g. stylized cinematic 3D illustration, soft lighting", oninput: (e) => (form.settings.style_prompt = e.target.value) })),
          el("div", { class: "three" },
            field("Keyframe candidates", select([[1, "1"], [2, "2"], [3, "3"], [4, "4"]], 2, (v) => (form.settings.keyframe_candidates = Number(v)))),
            field("Seed", el("input", { type: "number", value: 42, oninput: (e) => (form.settings.seed = Number(e.target.value)) })),
            field("Music", select([["off", "Off"], ["procedural", "Procedural bed"]], "off", setS("music_engine")))),
          el("div", { class: "row", style: "margin-top:8px" },
            el("button", { class: "btn primary", onclick: async (e) => {
              e.target.disabled = true;
              try {
                const b = await post("/storyboards", { title: form.title || "Untitled", script_text: form.script, target_duration_s: form.duration, settings: form.settings });
                location.hash = `#/board/${b.id}`;
              } finally { e.target.disabled = false; }
            } }, "Plan shots →"),
            el("span", { class: "hint" }, "Creates the shot list. Generation is per shot, on demand.")))));
    return page;
  };

  // ---------------------------------------------------------------- Storyboard workspace
  async function refreshBoard() {
    if (!state.activeBoard) return;
    try {
      const fresh = await get(`/storyboards/${state.activeBoard.id}`, { silent: true });
      const changed = JSON.stringify(fresh.shots.map((s) => [s.id, s.selected_keyframe_id, s.selected_clip_id, s.selected_speech_id, s.candidates.length, s.updated_at])) !== JSON.stringify(state.activeBoard.shots.map((s) => [s.id, s.selected_keyframe_id, s.selected_clip_id, s.selected_speech_id, s.candidates.length, s.updated_at]))
        || fresh.renders.length !== state.activeBoard.renders.length || JSON.stringify(fresh.jobs.map((j) => j.status)) !== JSON.stringify(state.activeBoard.jobs.map((j) => j.status));
      state.activeBoard = fresh;
      const typing = document.activeElement && document.activeElement.closest(".ws-inspector");
      if (changed && !typing) renderWorkspace();
      else if (changed) renderShotListOnly();
    } catch {}
  }
  routes.board = async ([id]) => {
    if (!state.engines) await loadEngines();
    state.activeBoard = await get(`/storyboards/${id}`);
    state.activeShot = state.activeShot && state.activeBoard.shots.some((s) => s.id === state.activeShot) ? state.activeShot : state.activeBoard.shots[0]?.id;
    return renderWorkspace(true);
  };
  const shotJobs = (shotId) => (state.activeBoard?.jobs || []).filter((j) => j.shot_id === shotId);
  const shotBusy = (shotId) => shotJobs(shotId).some((j) => j.status === "RUNNING" || j.status === "PENDING");
  const boardBusy = () => (state.activeBoard?.jobs || []).some((j) => j.status === "RUNNING" || j.status === "PENDING");
  const selCand = (shot, kind) => shot.candidates.find((c) => c.id === shot[`selected_${kind}_id`]);

  function renderWorkspace(fresh = false) {
    const b = state.activeBoard;
    const shot = b.shots.find((s) => s.id === state.activeShot) || b.shots[0];
    if (shot) state.activeShot = shot.id;
    const ws = el("div", { class: "ws" },
      el("div", { class: "ws-shots" }, renderTopBar(b), renderShotList(b)),
      el("div", { class: "ws-main" }, shot ? renderShotMain(b, shot) : el("div", { class: "empty-state" }, "Add a shot to begin.")),
      el("div", { class: "ws-inspector inspector" }, shot ? renderInspector(b, shot) : null));
    if (!fresh) { const v = $("#view"); const scroll = v.querySelector(".ws-main")?.scrollTop; v.replaceChildren(ws); if (scroll) ws.querySelector(".ws-main").scrollTop = scroll; }
    return ws;
  }

  function renderTopBar(b) {
    const busy = boardBusy();
    const missingKf = b.shots.filter((s) => !s.selected_keyframe_id).length;
    const missingClip = b.shots.filter((s) => !s.selected_clip_id).length;
    return el("div", { class: "ws-top", style: "flex-direction:column;align-items:stretch;gap:8px" },
      el("div", { class: "row" },
        el("a", { class: "btn ghost sm", href: "#/home" }, "←"),
        el("h2", { class: "grow", title: b.title, ondblclick: () => renameBoard(b) }, b.title),
        badge(b.status.toLowerCase(), b.status === "RENDERED" ? "ok" : "")),
      el("div", { class: "row" },
        el("button", { class: "btn sm primary grow", disabled: busy, onclick: () => generateAll(b) }, busy ? "Working…" : `Generate all${missingKf || missingClip ? ` (${missingKf} kf · ${missingClip} clips)` : ""}`),
        el("button", { class: "btn sm", disabled: busy || missingClip > 0, title: missingClip ? `${missingClip} shot(s) still need a clip` : "Assemble master", onclick: () => assemble(b) }, "Assemble"),
        el("button", { class: "btn sm ghost", onclick: () => boardSettings(b) }, "⚙")),
      b.renders.length ? el("div", { class: "row" }, el("button", { class: "btn sm ghost grow", onclick: () => showRenders(b) }, `▶ ${b.renders.length} render${b.renders.length > 1 ? "s" : ""} · latest ${fmtTime(b.renders[0].created_at)}`)) : null);
  }

  function renderShotList(b) {
    const list = el("div", { class: "shot-list" });
    let dragId = null;
    for (const s of b.shots) {
      const kf = selCand(s, "keyframe");
      const busy = shotBusy(s.id);
      const failed = shotJobs(s.id).some((j) => j.status.startsWith("FAILED"));
      const item = el("div", { class: `shot-item ${s.id === state.activeShot ? "active" : ""}`, draggable: true,
        onclick: () => { state.activeShot = s.id; renderWorkspace(); },
        ondragstart: (e) => { dragId = s.id; e.dataTransfer.effectAllowed = "move"; item.classList.add("dragging"); },
        ondragend: () => item.classList.remove("dragging"),
        ondragover: (e) => e.preventDefault(),
        ondrop: async (e) => { e.preventDefault(); if (!dragId || dragId === s.id) return; const ids = b.shots.map((x) => x.id); const from = ids.indexOf(dragId); const to = ids.indexOf(s.id); ids.splice(to, 0, ids.splice(from, 1)[0]); state.activeBoard = await post(`/storyboards/${b.id}/reorder`, { ordered_ids: ids }); renderWorkspace(); } },
        kf ? el("img", { class: "th", src: stream(kf.file_path) }) : el("div", { class: "th" }, busy ? "…" : s.position),
        el("div", { class: "ti" },
          el("div", { class: "n" }, el("span", {}, `${s.position}. ${s.speaker || s.framing.replace(/_/g, " ")}`), el("span", { class: "muted" }, `${Number(s.duration_s).toFixed(1)}s`)),
          el("div", { class: "a" }, s.dialogue ? `“${s.dialogue}”` : s.action),
          el("div", { class: "st" },
            el("i", { class: `dot ${busy ? "run" : s.selected_keyframe_id ? "ok" : failed ? "err" : ""}`, title: "keyframe" }),
            el("i", { class: `dot ${busy ? "run" : s.selected_clip_id ? "ok" : failed ? "err" : ""}`, title: "clip" }),
            s.dialogue ? el("i", { class: `dot ${s.selected_speech_id ? "ok" : ""}`, title: "speech" }) : null,
            el("span", { class: "muted small", style: "margin-left:auto" }, s.engine === "auto" ? "auto" : s.engine))));
      list.append(item);
    }
    list.append(el("button", { class: "btn sm ghost", style: "margin:4px", onclick: async () => { const last = b.shots[b.shots.length - 1]; const s = await post(`/storyboards/${b.id}/shots`, { after_shot_id: last?.id, heading: last?.heading || "", keyframe_source: last ? "inherit" : "flux" }); state.activeBoard = await get(`/storyboards/${b.id}`); state.activeShot = s.id; renderWorkspace(); } }, "＋ Add shot"));
    return list;
  }

  function renderShotMain(b, s) {
    const kf = selCand(s, "keyframe");
    const clip = selCand(s, "clip");
    const speech = selCand(s, "speech");
    const busy = shotBusy(s.id);
    const running = shotJobs(s.id).find((j) => j.status === "RUNNING");
    const prog = running ? state.progress[running.id] : null;
    const preview = el("div", { class: "preview" },
      clip ? el("video", { src: stream(clip.file_path), controls: true, loop: true, muted: true, autoplay: true, playsinline: true })
        : kf ? el("img", { src: stream(kf.file_path), onclick: () => lightbox(stream(kf.file_path)) })
        : el("div", { class: "empty" }, busy ? "Generating…" : "No keyframe yet. Generate one on the right, or pick an image from the Library."));
    const keyframes = s.candidates.filter((c) => c.kind === "keyframe");
    const clips = s.candidates.filter((c) => c.kind === "clip");
    const speeches = s.candidates.filter((c) => c.kind === "speech");
    const candCard = (c, kind) => {
      const isSel = s[`selected_${kind}_id`] === c.id;
      const media = kind === "clip" ? el("video", { src: stream(c.file_path), muted: true, loop: true, playsinline: true, onmouseenter: (e) => e.target.play(), onmouseleave: (e) => e.target.pause() }) : el("img", { src: stream(c.file_path), loading: "lazy" });
      const score = c.scores?.identity_similarity != null ? badge(`ID ${Number(c.scores.identity_similarity).toFixed(2)}`, c.scores.identity_similarity >= 0.8 ? "ok" : "warn") : null;
      return el("div", { class: `thumb-card ${kind === "clip" ? "clipcard" : ""} ${isSel ? "sel" : ""}`, onclick: async () => { if (!isSel) { await post(`/storyboards/candidates/${c.id}/select`); state.activeBoard = await get(`/storyboards/${b.id}`); renderWorkspace(); } } },
        media, score ? el("span", { class: "score" }, score) : null,
        el("div", { class: "cap" }, el("div", { class: "t" }, c.engine || kind), el("div", { class: "m" }, c.seed != null ? `seed ${c.seed}` : "", c.duration_s ? ` · ${Number(c.duration_s).toFixed(1)}s` : "")),
        el("div", { class: "ov" },
          el("button", { class: "btn xs", onclick: (e) => { e.stopPropagation(); lightbox(stream(c.file_path), kind === "clip"); } }, "view"),
          kind === "keyframe" && c.asset_id ? el("button", { class: "btn xs", onclick: (e) => { e.stopPropagation(); location.hash = `#/editor/${c.asset_id}/${s.id}`; } }, "edit") : null));
    };
    return el("div", {},
      el("div", { class: "row", style: "margin-bottom:10px" },
        el("h2", { style: "margin:0;font-size:16px" }, `Shot ${s.position}`, el("span", { class: "muted" }, ` · ${s.label}`)),
        el("span", { class: "grow" }),
        clip ? badge(`clip · ${clip.engine}`, "ok") : badge("no clip"), kf ? badge("keyframe", "ok") : badge("no keyframe"), s.dialogue ? (speech ? badge(`voice ${Number(speech.duration_s).toFixed(1)}s`, "ok") : badge("no voice")) : null),
      preview,
      running && prog ? el("div", {}, el("div", { class: "small muted" }, `${prog.stage} · ${prog.progress}% · ${Math.round(prog.elapsed_s)}s`), el("div", { class: "prog" }, el("i", { style: `width:${prog.progress}%` }))) : null,
      el("div", { class: "section" },
        el("div", { class: "section-h" }, el("h3", {}, `Keyframes (${keyframes.length})`), el("div", { class: "row" },
          el("button", { class: "btn sm", disabled: busy, onclick: () => pickFromLibrary(s) }, "From library"),
          el("button", { class: "btn sm", disabled: busy, onclick: () => genKeyframes(s, 2) }, "＋ 2 more"))),
        keyframes.length ? el("div", { class: "strip" }, ...keyframes.map((c) => candCard(c, "keyframe"))) : el("div", { class: "muted small" }, "No candidates yet.")),
      el("div", { class: "section" },
        el("div", { class: "section-h" }, el("h3", {}, `Clips (${clips.length})`), el("div", { class: "row" },
          ...["2.5d", "ltx", "h3"].map((e) => el("button", { class: "btn sm", disabled: busy || !kf || !state.engines?.[e]?.available, title: state.engines?.[e]?.note || "", onclick: () => genClip(s, e) }, `Render ${state.engines?.[e]?.label?.split(" ")[0] || e}`)))),
        clips.length ? el("div", { class: "strip" }, ...clips.map((c) => candCard(c, "clip"))) : el("div", { class: "muted small" }, "Render motion from the selected keyframe.")),
      s.dialogue ? el("div", { class: "section" },
        el("div", { class: "section-h" }, el("h3", {}, `Voice (${speeches.length})`), el("button", { class: "btn sm", disabled: busy, onclick: () => post(`/storyboards/shots/${s.id}/speech`).then(() => toast("Voice queued")) }, "Regenerate voice")),
        speeches.length ? el("div", { class: "row" }, ...speeches.map((c) => el("div", { class: `card card-pad ${s.selected_speech_id === c.id ? "sel" : ""}`, style: `padding:8px 10px;${s.selected_speech_id === c.id ? "border-color:var(--accent)" : ""}` },
          el("audio", { src: stream(c.file_path), controls: true, style: "height:30px" }), el("div", { class: "small muted" }, `${c.engine} · ${Number(c.duration_s).toFixed(1)}s`)))) : el("div", { class: "muted small" }, "No voice yet.")) : null);
  }

  function renderInspector(b, s) {
    const busy = shotBusy(s.id);
    let pending = {};
    let timer = null;
    const save = async () => { if (!Object.keys(pending).length) return; const p = pending; pending = {}; const updated = await patch(`/storyboards/shots/${s.id}`, p); Object.assign(s, updated); renderShotListOnly(); };
    const queue = (k, v) => { pending[k] = v; clearTimeout(timer); timer = setTimeout(save, 500); };
    const engines = state.engines || {};
    const engineOpts = [["auto", "Auto (dialogue → 2.5D, else LTX)"], ...Object.entries(engines).map(([k, e]) => [k, `${e.label}${e.available ? "" : " — unavailable"}`, !e.available])];
    const failed = shotJobs(s.id).filter((j) => j.status.startsWith("FAILED"))[0];
    return el("div", {},
      el("h3", {}, "Shot settings"),
      field("Action / visual description", el("textarea", { style: "min-height:80px", oninput: (e) => queue("action", e.target.value) }, s.action)),
      field("Scene heading", el("input", { type: "text", value: s.heading, oninput: (e) => queue("heading", e.target.value) })),
      el("div", { class: "two" },
        field("Speaker", el("input", { type: "text", value: s.speaker, oninput: (e) => queue("speaker", e.target.value) })),
        field("Duration (s)", el("input", { type: "number", min: 1, max: 12, step: 0.5, value: s.duration_s, onchange: (e) => queue("duration_s", Number(e.target.value)) }))),
      field("Dialogue", el("textarea", { style: "min-height:56px", oninput: (e) => queue("dialogue", e.target.value) }, s.dialogue)),
      el("div", { class: "two" },
        field("Framing", select([["wide_establishing", "Wide establishing"], ["medium", "Medium"], ["medium_close_up", "Medium close-up"], ["hero_close_up", "Hero close-up"], ["dramatic_push_insert", "Insert"], ["wide_dynamic", "Wide dynamic"]], s.framing, (v) => queue("framing", v))),
        field("Seed", el("input", { type: "number", value: s.seed ?? "", placeholder: "auto", onchange: (e) => queue("seed", e.target.value === "" ? null : Number(e.target.value)) }))),
      field("Keyframe source", select([["flux", "Generate with FLUX"], ["inherit", "Inherit previous shot's keyframe"], ["reference", "Use a library image"]], s.keyframe_source, (v) => queue("keyframe_source", v)), s.reference_asset_id ? `Reference: ${s.reference_asset_id}` : null),
      el("div", { class: "insp-actions" },
        el("button", { class: "btn primary", disabled: busy, onclick: () => genKeyframes(s) }, "Generate keyframes"),
        s.dialogue ? el("button", { class: "btn", disabled: busy, onclick: () => post(`/storyboards/shots/${s.id}/speech`).then(() => toast("Voice queued")) }, "Voice") : el("span")),
      el("h3", { style: "margin-top:10px" }, "Motion"),
      field("Engine", select(engineOpts, s.engine, (v) => queue("engine", v)), engines[s.engine]?.note),
      s.engine === "2.5d" || s.engine === "auto" ? field("Camera move (2.5D)", select([["push_in", "Push in"], ["pull_out", "Pull out"], ["pan_left", "Pan left"], ["pan_right", "Pan right"], ["tilt_up", "Tilt up"], ["tilt_down", "Tilt down"], ["static", "Static"]], s.camera_motion, (v) => queue("camera_motion", v))) : null,
      el("div", { class: "insp-actions" },
        el("button", { class: "btn primary", disabled: busy || !s.selected_keyframe_id, title: s.selected_keyframe_id ? "" : "Select a keyframe first", onclick: () => genClip(s) }, "Render clip"),
        el("button", { class: "btn danger", onclick: async () => { if (await confirmDlg("Delete this shot and its candidates?")) { await del(`/storyboards/shots/${s.id}`); state.activeBoard = await get(`/storyboards/${b.id}`); state.activeShot = null; renderWorkspace(); } } }, "Delete shot")),
      failed ? el("div", { class: "card card-pad", style: "border-color:rgba(248,113,113,.4);font-size:12px" }, el("div", { style: "color:var(--err);font-weight:600;margin-bottom:4px" }, "Last job failed"), el("div", { class: "mono" }, (failed.error_message || "").split("\n")[0])) : null,
      field("Notes", el("textarea", { style: "min-height:50px", oninput: (e) => queue("notes", e.target.value) }, s.notes || "")));
  }
  function renderShotListOnly() { const list = $(".ws-shots"); if (list) list.replaceChildren(renderTopBar(state.activeBoard), renderShotList(state.activeBoard)); }

  async function genKeyframes(s, count) {
    await post(`/storyboards/shots/${s.id}/keyframes`, { count: count || state.activeBoard.settings.keyframe_candidates || 2 });
    toast("Keyframes queued"); state._hadActivity = true; await pollGlobal();
  }
  async function genClip(s, engine) {
    await post(`/storyboards/shots/${s.id}/clip`, { engine: engine || null });
    toast(`Clip queued (${engine || s.engine})`); state._hadActivity = true; await pollGlobal();
  }
  async function generateAll(b) {
    const r = await post(`/storyboards/${b.id}/batch`, { keyframes: true, speech: true, clips: true, assemble: false, only_missing: true });
    toast(`${r.queued} job(s) queued`); state._hadActivity = true; await pollGlobal();
  }
  async function assemble(b) {
    await post(`/storyboards/${b.id}/assemble`, { settings: {} });
    toast("Assembly queued"); state._hadActivity = true; await pollGlobal();
  }
  async function renameBoard(b) {
    const t = prompt("Title", b.title); if (!t) return;
    state.activeBoard = await patch(`/storyboards/${b.id}`, { title: t }); renderWorkspace();
  }
  function boardSettings(b) {
    const s = { ...b.settings };
    const set = (k) => (v) => (s[k] = v);
    const body = el("div", {},
      el("div", { class: "two" },
        field("Aspect", select([["9:16", "9:16"], ["16:9", "16:9"], ["1:1", "1:1"]], s.aspect_ratio, set("aspect_ratio")), "Changing aspect requires regenerating keyframes."),
        field("Quality", select([["draft", "Draft"], ["balanced", "Balanced"], ["quality", "Quality"]], s.quality_profile, set("quality_profile")))),
      el("div", { class: "two" },
        field("Genre", select([["cyberpunk_thriller", "Cyberpunk thriller"], ["suspense_drama", "Suspense drama"], ["romance_cinematic", "Romantic"], ["action_chase", "Action"]], s.genre, set("genre"))),
        field("Seed", el("input", { type: "number", value: s.seed, oninput: (e) => (s.seed = Number(e.target.value)) }))),
      field("Style prompt", el("input", { type: "text", value: s.style_prompt || "", oninput: (e) => (s.style_prompt = e.target.value) })),
      el("div", { class: "three" },
        field("Voice", select(engineOptions(state.voiceEngines, s.voice_engine), s.voice_engine, set("voice_engine")), state.voiceEngines?.[s.voice_engine]?.note),
        field("Music", select(engineOptions(state.musicEngines, s.music_engine), s.music_engine, set("music_engine")), state.musicEngines?.[s.music_engine]?.note),
        field("Foley", select([["off", "Off"], ["library", "Library SFX"]], s.foley_engine, set("foley_engine")))),
      s.music_engine === "ace_step" || true ? field("Music prompt (ACE-Step)", el("input", { type: "text", value: s.music_prompt || "", placeholder: "e.g. tense cyberpunk synth underscore, no vocals", oninput: (e) => (s.music_prompt = e.target.value) })) : null,
      field("Frame interpolation", select([["off", "Off (24 fps)"], ["film_2x", "FILM 2x (48 fps)"]], s.frame_interpolation, set("frame_interpolation"))),
      el("div", { class: "two" },
        field("Subtitles", select([["true", "Burn in"], ["false", "Off"]], String(s.burn_subtitles), (v) => (s.burn_subtitles = v === "true"))),
        field("Keyframe candidates", select([[1, "1"], [2, "2"], [3, "3"], [4, "4"]], s.keyframe_candidates, (v) => (s.keyframe_candidates = Number(v))))),
      el("div", { class: "row" }, el("button", { class: "btn primary", onclick: async () => { state.activeBoard = await patch(`/storyboards/${b.id}`, { settings: s }); close(); renderWorkspace(); toast("Settings saved", "ok"); } }, "Save"),
        el("button", { class: "btn danger ghost", style: "margin-left:auto", onclick: async () => { if (await confirmDlg("Delete this storyboard and all its shots?")) { await del(`/storyboards/${b.id}`); close(); location.hash = "#/home"; } } }, "Delete storyboard")));
    const close = modal("Storyboard settings", body);
  }
  function showRenders(b) {
    const body = el("div", { class: "grid cols-3" }, ...b.renders.map((r) => el("div", { class: "card" },
      el("video", { src: stream(r.master_video_path), controls: true, style: "width:100%;aspect-ratio:9/16;background:#000;border-radius:10px 10px 0 0" }),
      el("div", { class: "card-pad" },
        el("div", { class: "row" }, badge(`${Number(r.duration_s).toFixed(1)}s`), r.qa?.visual_dino_score != null ? badge(`DINO ${r.qa.visual_dino_score.toFixed(3)}`, r.qa.visual_dino_score >= 0.8 ? "ok" : "warn") : null, ...(r.qa?.engines_used || []).map((e) => badge(e, "accent"))),
        el("div", { class: "small muted", style: "margin-top:6px" }, fmtTime(r.created_at)),
        el("div", { class: "row", style: "margin-top:8px" }, el("a", { class: "btn sm", href: stream(r.master_video_path), download: `${b.title.replace(/\s+/g, "_")}.mp4` }, "⬇ Download"),
          r.srt_path ? el("a", { class: "btn sm ghost", href: stream(r.srt_path), download: "captions.srt" }, "SRT") : null),
        r.thumbnails?.length ? el("div", { class: "row", style: "margin-top:8px" }, ...r.thumbnails.slice(0, 3).map((t) => el("img", { src: stream(t), style: "height:56px;border-radius:6px;cursor:pointer", onclick: () => lightbox(stream(t)) }))) : null))));
    modal("Renders", body, { wide: true });
  }
  async function pickFromLibrary(s) {
    const { images } = await get("/media/images");
    const usable = images.filter((i) => i.asset_id);
    const body = el("div", {}, usable.length ? el("div", { class: "grid cols-6" }, ...usable.map((img) => el("div", { class: "thumb-card", onclick: async () => { await post(`/storyboards/shots/${s.id}/candidates/from-asset`, { asset_id: img.asset_id }); close(); state.activeBoard = await get(`/storyboards/${state.activeBoard.id}`); renderWorkspace(); toast("Keyframe set from library", "ok"); } },
      el("img", { src: stream(img.path), loading: "lazy" }), el("div", { class: "cap" }, el("div", { class: "t" }, img.name), el("div", { class: "m" }, img.source))))) : el("div", { class: "empty-state" }, "No library images yet. Upload or generate some in Library."));
    const close = modal("Use image as keyframe", body, { wide: true });
  }

  // ---------------------------------------------------------------- Library
  routes.library = async () => {
    let filter = "all";
    const grid = el("div", { class: "grid cols-6" });
    const load = async () => {
      const { images } = await get("/media/images");
      const items = images.filter((i) => filter === "all" || i.source === filter);
      grid.replaceChildren(...(items.length ? items.map((img) => el("div", { class: "thumb-card" },
        el("img", { src: stream(img.path), loading: "lazy", onclick: () => lightbox(stream(img.path)) }),
        el("span", { class: "badge tag" }, img.source),
        el("div", { class: "cap" }, el("div", { class: "t", title: img.name }, img.name), el("div", { class: "m" }, `${img.size_mb} MB · ${fmtTime(new Date(img.created_time * 1000).toISOString())}`)),
        el("div", { class: "ov" },
          img.asset_id ? el("button", { class: "btn xs", onclick: () => (location.hash = `#/editor/${img.asset_id}`) }, "Edit") : null,
          img.asset_id ? el("button", { class: "btn xs", onclick: () => useInStoryboard(img.asset_id) }, "Use in shot") : null,
          img.source === "upload" ? el("button", { class: "btn xs danger", onclick: async () => { if (await confirmDlg("Delete image?")) { await del("/media/image", { path: img.path }); load(); } } }, "Delete") : null))) : [el("div", { class: "empty-state", style: "grid-column:1/-1" }, "Nothing here yet.")]));
    };
    const upload = async (files) => { for (const f of files) { const fd = new FormData(); fd.append("file", f); await post("/media/upload", fd); } toast(`${files.length} uploaded`, "ok"); load(); };
    const fileInput = el("input", { type: "file", accept: ".jpg,.jpeg,.png,.webp", multiple: true, style: "display:none", onchange: (e) => upload([...e.target.files]) });
    const zone = el("div", { class: "upload-zone", onclick: () => fileInput.click(),
      ondragover: (e) => { e.preventDefault(); zone.classList.add("over"); }, ondragleave: () => zone.classList.remove("over"),
      ondrop: (e) => { e.preventDefault(); zone.classList.remove("over"); upload([...e.dataTransfer.files].filter((f) => /image/.test(f.type))); } },
      "Drop images here or click to upload — uploads become editable assets and can be used as shot keyframes or references.", fileInput);
    const gen = { prompt: "", aspect_ratio: "9:16", seed: 42 };
    const genBox = el("div", { class: "card card-pad", style: "margin-top:14px" },
      el("div", { class: "row" }, el("strong", {}, "Generate image"), badge("FLUX.2 Klein · verified", "ok")),
      el("div", { style: "display:grid;grid-template-columns:1fr 130px 110px auto;gap:8px;margin-top:8px;align-items:end" },
        field("Prompt", el("input", { type: "text", placeholder: "Describe the image…", oninput: (e) => (gen.prompt = e.target.value) })),
        field("Aspect", select([["9:16", "9:16"], ["16:9", "16:9"], ["1:1", "1:1"]], "9:16", (v) => (gen.aspect_ratio = v))),
        field("Seed", el("input", { type: "number", value: 42, oninput: (e) => (gen.seed = Number(e.target.value)) })),
        el("button", { class: "btn primary", style: "margin-bottom:12px", onclick: async (e) => { if (!gen.prompt.trim()) return toast("Enter a prompt", "err"); e.target.disabled = true; e.target.textContent = "Generating…"; try { await post("/creator/generate-image", gen); toast("Image generated", "ok"); load(); } finally { e.target.disabled = false; e.target.textContent = "Generate"; } } }, "Generate")));
    const filters = el("div", { class: "chips", style: "margin:16px 0 10px" }, ...[["all", "All"], ["upload", "Uploads"], ["generated", "Generated"], ["edited", "Edited"]].map(([k, l]) => el("button", { class: `chip ${k === filter ? "active" : ""}`, onclick: (e) => { filter = k; filters.querySelectorAll(".chip").forEach((c) => c.classList.remove("active")); e.target.classList.add("active"); load(); } }, l)));
    load();
    return el("div", { class: "page" }, el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "Library"), el("p", {}, "Uploads, generated images, keyframes and Qwen edits."))), zone, genBox, filters, grid);
  };
  async function useInStoryboard(assetId) {
    const { storyboards } = await get("/storyboards");
    if (!storyboards.length) return toast("Create a video first", "err");
    const sel = select(storyboards.map((b) => [b.id, b.title]), storyboards[0].id);
    const shotSel = el("select");
    const fill = async () => { const b = await get(`/storyboards/${sel.value}`); shotSel.replaceChildren(...b.shots.map((s) => el("option", { value: s.id }, `${s.position}. ${s.action.slice(0, 50)}`))); };
    sel.addEventListener("change", fill); await fill();
    const close = modal("Use image as shot keyframe", el("div", {}, field("Video", sel), field("Shot", shotSel),
      el("button", { class: "btn primary", onclick: async () => { await post(`/storyboards/shots/${shotSel.value}/candidates/from-asset`, { asset_id: assetId }); close(); toast("Keyframe set", "ok"); location.hash = `#/board/${sel.value}`; } }, "Use as keyframe")));
  }

  // ---------------------------------------------------------------- Image editor (Qwen)
  routes.editor = async ([assetId, returnShot]) => {
    const [sources, actions] = await Promise.all([get("/editor/sources"), get("/editor/actions")]);
    const qwen = (state.caps || (await get("/capabilities"))).engines.find((e) => e.id === "qwen_image_edit");
    let src = sources.find((s) => s.id === assetId) || sources[0];
    const preview = el("img", { style: "max-width:100%;max-height:62vh;display:block;margin:auto" });
    const result = el("div", { class: "muted small", style: "margin-top:8px" });
    const setPreview = () => { if (src) preview.src = stream(src.file_path); };
    const srcSel = select(sources.map((s) => [s.id, `${s.name} · ${s.kind}`]), src?.id, (v) => { src = sources.find((s) => s.id === v); setPreview(); });
    const actionSel = select(actions.map((a) => [a.action, a.action.replace(/_/g, " ")]), actions[0]?.action, (v) => { instr.value = actions.find((a) => a.action === v)?.default_instruction || ""; });
    const instr = el("textarea", { style: "min-height:90px" }, actions[0]?.default_instruction || "");
    const seed = el("input", { type: "number", value: 1000 });
    const run = el("button", { class: "btn primary", onclick: async () => {
      if (!src) return toast("Choose a source image", "err");
      run.disabled = true; const t0 = Date.now(); const tick = setInterval(() => (run.textContent = `Editing… ${Math.round((Date.now() - t0) / 1000)}s`), 1000);
      try {
        const r = await post("/editor/execute", { project_id: src.project_id, source_asset_id: src.id, action: actionSel.value, instruction: instr.value.trim(), seed: Number(seed.value) });
        preview.src = stream(r.file_path);
        const qa = r.provenance_json?.qa_metrics || {};
        result.replaceChildren(badge(qa.evaluation || "done", qa.identity_similarity >= 0.82 ? "ok" : "warn"), " ", qa.identity_similarity != null ? `DINO identity ${Number(qa.identity_similarity).toFixed(3)}` : "",
          returnShot ? el("button", { class: "btn sm", style: "margin-left:10px", onclick: async () => { await post(`/storyboards/shots/${returnShot}/candidates/from-asset`, { asset_id: r.id }); toast("Edited image set as keyframe", "ok"); history.back(); } }, "Use as keyframe →") : null);
        toast("Edit complete", "ok");
      } finally { clearInterval(tick); run.disabled = false; run.textContent = "Run Qwen edit"; }
    } }, "Run Qwen edit");
    setPreview();
    return el("div", { class: "page" },
      el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "Image editor"), el("p", {}, "Qwen Image Edit 2511 — identity-preserving edits. ", qwen ? badge(qwen.runtime.replace("_", " "), qwen.runtime === "verified" ? "ok" : "warn") : null, " Expect ~8 min per edit on this GPU.")),
        returnShot ? el("a", { class: "btn", href: `#/board/${state.activeBoard?.id || ""}`, onclick: (e) => { e.preventDefault(); history.back(); } }, "← Back to shot") : null),
      el("div", { style: "display:grid;grid-template-columns:360px 1fr;gap:18px" },
        el("div", { class: "card card-pad" }, field("Source image", srcSel), field("Edit type", actionSel), field("Instruction", instr, "Describe only the change; the rest is preserved."), field("Seed", seed), run),
        el("div", { class: "card card-pad" }, preview, result)));
  };

  // ---------------------------------------------------------------- Renders gallery
  routes.gallery = async () => {
    const [{ videos }, { storyboards }] = await Promise.all([get("/media/gallery"), get("/storyboards")]);
    const cards = videos.map((v) => el("div", { class: "thumb-card", onclick: () => lightbox(v.stream_url, true) },
      v.thumb_url ? el("img", { src: v.thumb_url, loading: "lazy" }) : el("video", { src: v.stream_url, preload: "metadata", muted: true }),
      el("div", { class: "cap" }, el("div", { class: "t" }, v.title), el("div", { class: "m" }, `${v.size_mb} MB · ${fmtTime(new Date(v.created_time * 1000).toISOString())}`)),
      el("div", { class: "ov" }, el("a", { class: "btn xs", href: v.stream_url, download: true, onclick: (e) => e.stopPropagation() }, "Download"))));
    return el("div", { class: "page" }, el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "Renders"), el("p", {}, `${videos.length} master videos across ${storyboards.length} storyboards and legacy runs.`))),
      cards.length ? el("div", { class: "grid cols-6" }, ...cards) : el("div", { class: "card empty-state" }, "No renders yet."));
  };

  // ---------------------------------------------------------------- Engines
  routes.engines = async () => {
    const caps = await get("/capabilities"); state.caps = caps;
    const s = caps.summary;
    const kind = (r) => ({ verified: "ok", installed_unverified: "warn", runtime_blocked: "warn", missing_weights: "err" }[r] || "");
    return el("div", { class: "page" },
      el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "Engines"), el("p", {}, `${s.verified_engines} verified · ${s.blocked_engines} installed but not verified · ${s.missing_engines} missing weights · ${s.installed_weight_files} weight files on disk · ${s.free_disk_gib} GB free`))),
      el("div", { class: "grid cols-3" }, ...caps.engines.map((e) => el("div", { class: "card engine-card" },
        el("div", { class: "row" }, el("h4", { class: "grow" }, e.label), badge(e.runtime.replace(/_/g, " "), kind(e.runtime))),
        el("div", { class: "row" }, badge(e.stage), badge(`${e.size_gib} GiB`), badge(e.backend), e.verified_at ? badge(`verified ${e.verified_at}`, "ok") : null),
        el("p", {}, e.note),
        e.runtime !== "verified" && e.setup_hint ? el("div", { class: "hint" }, e.setup_hint) : null))),
      el("h3", { style: "margin:22px 0 8px;font-size:13px;color:var(--text-2)" }, "Always-available fallbacks"),
      el("div", { class: "row" }, ...caps.fallbacks.map((f) => badge(`${f.stage}: ${f.label}`))));
  };

  // ---------------------------------------------------------------- Boot
  loadEngines().then(navigate);
  pollGlobal(); setInterval(pollGlobal, 2500);
})();
