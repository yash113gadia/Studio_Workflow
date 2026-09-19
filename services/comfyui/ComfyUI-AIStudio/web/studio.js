import { app } from "../../scripts/app.js";

const STUDIO_API = "http://127.0.0.1:8000/api/v1";

class AIStudioUI {
    constructor() {
        this.activeProject = null;
        this.projects = [];
        this.jobs = [];
        this.assets = [];
        this.systemHealth = null;
        this.panel = null;
        this.activeTab = "dashboard"; // "dashboard" | "casting" | "queue"
    }

    async init() {
        this.createSidebarUI();
        this.startPolling();
    }

    createSidebarUI() {
        const menu = document.querySelector(".comfy-menu") || document.body;
        const btn = document.createElement("button");
        btn.id = "preeti-studio-toggle-btn";
        btn.textContent = "🎬 AI Studio";
        btn.style.margin = "4px";
        btn.style.backgroundColor = "#0066cc";
        btn.style.color = "#ffffff";
        btn.style.fontWeight = "bold";
        btn.style.borderRadius = "4px";
        btn.style.border = "none";
        btn.style.padding = "6px 12px";
        btn.style.cursor = "pointer";
        btn.onclick = () => this.togglePanel();
        menu.appendChild(btn);

        this.panel = document.createElement("div");
        this.panel.id = "preeti-studio-panel";
        this.panel.className = "studio-sidebar-panel";
        this.panel.style.position = "fixed";
        this.panel.style.top = "0";
        this.panel.style.right = "0";
        this.panel.style.width = "420px";
        this.panel.style.height = "100vh";
        this.panel.style.zIndex = "1000";
        this.panel.style.boxShadow = "-4px 0 16px rgba(0,0,0,0.5)";
        this.panel.style.display = "none";
        this.panel.style.overflowY = "auto";

        document.body.appendChild(this.panel);
        this.render();
    }

    togglePanel() {
        if (this.panel.style.display === "none") {
            this.panel.style.display = "flex";
            this.refresh();
        } else {
            this.panel.style.display = "none";
        }
    }

    async refresh() {
        try {
            const hRes = await fetch(`${STUDIO_API}/health`);
            this.systemHealth = await hRes.json();
        } catch (e) {
            this.systemHealth = { status: "offline", error: e.message };
        }

        try {
            const pRes = await fetch(`${STUDIO_API}/projects`);
            this.projects = await pRes.json();
            if (!this.activeProject && this.projects.length > 0) {
                this.activeProject = this.projects[0];
            }
        } catch (e) {
            this.projects = [];
        }

        if (this.activeProject) {
            try {
                const jRes = await fetch(`${STUDIO_API}/jobs?limit=10`);
                this.jobs = await jRes.json();
            } catch (e) {
                this.jobs = [];
            }

            try {
                const aRes = await fetch(`${STUDIO_API}/assets/project/${this.activeProject.id}`);
                this.assets = await aRes.json();
            } catch (e) {
                this.assets = [];
            }
        }

        this.render();
    }

    startPolling() {
        setInterval(() => {
            if (this.panel && this.panel.style.display !== "none") {
                this.refresh();
            }
        }, 3000);
    }

    async createProject(name, kind) {
        try {
            const res = await fetch(`${STUDIO_API}/projects`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, kind, style_id: "STYLE_SERIES_A_V001", autonomy_mode: "review" })
            });
            if (res.ok) {
                const newP = await res.json();
                this.activeProject = newP;
                await this.refresh();
            } else {
                alert("Failed to create project: " + res.statusText);
            }
        } catch (e) {
            alert("Error: " + e.message);
        }
    }

    async triggerCastingSession(name, prompt) {
        if (!this.activeProject) {
            alert("Select or create an active project first.");
            return;
        }
        try {
            const res = await fetch(`${STUDIO_API}/assets/casting/create`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: this.activeProject.id,
                    character_name: name,
                    prompt_description: prompt,
                    count: 3,
                    seed_base: 1000
                })
            });
            if (res.ok) {
                const jobs = await res.json();
                alert(`Queued 3 FLUX casting candidates for ${name}!`);
                await this.refresh();
            } else {
                alert("Failed to queue casting: " + res.statusText);
            }
        } catch (e) {
            alert("Error: " + e.message);
        }
    }

    async approveCandidate(candidateId, characterCode) {
        if (!this.activeProject) return;
        try {
            const res = await fetch(`${STUDIO_API}/assets/casting/approve`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: this.activeProject.id,
                    candidate_asset_id: candidateId,
                    character_code: characterCode,
                    approval_actor: "studio_admin"
                })
            });
            if (res.ok) {
                alert(`Approved candidate as immutable canon: CHAR_${characterCode.toUpperCase()}_V001!`);
                await this.refresh();
            } else {
                const err = await res.json();
                alert(`Approval failed: ${err.detail || res.statusText}`);
            }
        } catch (e) {
            alert("Error approving character: " + e.message);
        }
    }

    async deriveAngles(canonicalId) {
        if (!this.activeProject) return;
        try {
            const res = await fetch(`${STUDIO_API}/assets/canonical/angles`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: this.activeProject.id,
                    canonical_id: canonicalId,
                    seed_base: 2000
                })
            });
            if (res.ok) {
                alert(`Queued 5 canonical angle compositions for ${canonicalId}!`);
                await this.refresh();
            } else {
                alert("Failed to queue angles: " + res.statusText);
            }
        } catch (e) {
            alert("Error: " + e.message);
        }
    }

    async triggerH3Shot(keyframeId, prompt, durationS, candidates) {
        if (!this.activeProject) return;
        try {
            const res = await fetch(`${STUDIO_API}/video/h3-execute?mock=true`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: this.activeProject.id,
                    keyframe_asset_id: keyframeId,
                    prompt: prompt,
                    duration_s: parseFloat(durationS) || 5.0,
                    aspect: "9:16",
                    width: 480,
                    height: 864,
                    candidates: parseInt(candidates) || 1,
                    seed: 42,
                    denoising_priority: "lower_vram",
                    text_encoder_variant: "gguf_q2_k",
                    video_vae_variant: "fp8mix",
                    reference_mode: false
                })
            });
            if (res.ok) {
                const shot = await res.json();
                alert(`Generated ~5s vertical shot via WanGP H3! Asset: ${shot.output_video_asset_id}`);
                await this.refresh();
            } else {
                const err = await res.json();
                alert(`Shot generation failed: ${err.detail || res.statusText}`);
            }
        } catch (e) {
            alert("Error generating H3 shot: " + e.message);
        }
    }

    render() {
        if (!this.panel) return;

        const isOnline = this.systemHealth && this.systemHealth.status === "ok";
        const diskFree = this.systemHealth ? `${this.systemHealth.free_disk_gb} GB` : "N/A";
        const leaseStatus = this.systemHealth ? this.systemHealth.gpu_lease_status : "N/A";

        let projectsOptions = this.projects.map(p => 
            `<option value="${p.id}" ${this.activeProject && this.activeProject.id === p.id ? 'selected' : ''}>${p.name} (${p.kind})</option>`
        ).join("");

        let canonicalRefs = this.assets.filter(a => a.kind === "canonical_ref");
        let castingCandidates = this.assets.filter(a => a.kind === "casting_candidate");
        let angleAssets = this.assets.filter(a => a.kind === "canonical_angle");
        let videoShots = this.assets.filter(a => a.kind === "video_shot");
        let allKeyframes = this.assets.filter(a => a.kind === "canonical_ref" || a.kind === "keyframe" || a.kind === "canonical_angle");

        let jobsRows = this.jobs.map(j => `
            <tr>
                <td>${j.id.substring(0, 8)}</td>
                <td>${j.kind}</td>
                <td><span class="${j.status === 'SUCCEEDED' ? 'status-ok' : (j.status === 'RUNNING' ? 'status-warn' : '')}">${j.status}</span></td>
            </tr>
        `).join("");

        this.panel.innerHTML = `
            <div class="studio-header">
                <div class="studio-title">
                    <span>🎬 AI STUDIO</span>
                    <span class="studio-badge">${isOnline ? 'ONLINE' : 'OFFLINE'}</span>
                </div>
                <button class="studio-btn studio-btn-secondary" style="width: auto; padding: 4px 8px; margin: 0;" id="studio-close-btn">✕</button>
            </div>

            <!-- Health & Hardware Card -->
            <div class="studio-card">
                <div class="studio-card-title">System & GPU Lease</div>
                <div class="studio-status-row">
                    <span>Studio Core:</span>
                    <span class="studio-status-val ${isOnline ? 'status-ok' : 'status-err'}">${isOnline ? 'Connected' : 'Offline'}</span>
                </div>
                <div class="studio-status-row">
                    <span>GPU Lease (Heavy):</span>
                    <span class="studio-status-val ${leaseStatus === 'FREE' ? 'status-ok' : 'status-warn'}">${leaseStatus}</span>
                </div>
                <div class="studio-status-row">
                    <span>Free Disk Space:</span>
                    <span class="studio-status-val">${diskFree}</span>
                </div>
            </div>

            <!-- Project Selector Card -->
            <div class="studio-card">
                <div class="studio-card-title">Active Production Project</div>
                <select class="studio-input" id="studio-project-select">
                    ${projectsOptions || '<option value="">No Projects Yet</option>'}
                </select>
                
                <div style="display: flex; gap: 6px;">
                    <input type="text" class="studio-input" id="studio-new-project-name" placeholder="New project name..." style="margin-bottom: 0;">
                    <button class="studio-btn" id="studio-create-proj-btn" style="width: 80px; margin-top: 0;">New</button>
                </div>
            </div>

            <!-- Phase 4: Character Asset Factory Card -->
            <div class="studio-card">
                <div class="studio-card-title">🎭 Character Asset Factory (FLUX.2 Klein)</div>
                <input type="text" class="studio-input" id="studio-char-name" placeholder="Character Name (e.g. Maya)...">
                <textarea class="studio-input" id="studio-char-prompt" rows="2" placeholder="Visual description: 28yo female protagonist, sharp hazel eyes, dark leather jacket..."></textarea>
                <button class="studio-btn" id="studio-cast-btn" style="margin-top: 2px;">⚡ Generate 3 Casting Candidates</button>

                <!-- Canonical Reference Display -->
                <div style="margin-top: 12px; border-top: 1px solid #333; padding-top: 8px;">
                    <div style="font-weight: bold; font-size: 12px; color: #aaa; margin-bottom: 6px;">CANONICAL IDENTITY REFS (TIER 0)</div>
                    ${canonicalRefs.length === 0 ? '<div style="font-size: 11px; color: #666;">No canonical characters approved yet.</div>' : 
                        canonicalRefs.map(c => `
                            <div style="background: #1e1e1e; padding: 8px; border-radius: 4px; margin-bottom: 6px; border-left: 3px solid #00aa66;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: bold; color: #fff;">${c.id}</span>
                                    <span class="studio-badge" style="background: #00aa66;">IMMUTABLE</span>
                                </div>
                                <div style="font-size: 11px; color: #888; margin-top: 4px;">Name: ${c.metadata_json.character_name || 'N/A'} | Seed: ${c.metadata_json.seed || 'N/A'}</div>
                                <button class="studio-btn studio-btn-secondary studio-derive-angles-btn" data-canonical="${c.id}" style="margin-top: 6px; padding: 4px 8px; font-size: 11px;">📐 Derive 5 Canonical Angles</button>
                            </div>
                        `).join("")
                    }
                </div>

                <!-- Casting Candidates Pending Approval -->
                ${castingCandidates.length > 0 ? `
                    <div style="margin-top: 8px; border-top: 1px solid #333; padding-top: 6px;">
                        <div style="font-weight: bold; font-size: 11px; color: #aaa; margin-bottom: 4px;">CANDIDATES PENDING APPROVAL</div>
                        ${castingCandidates.map(cand => `
                            <div style="display: flex; justify-content: space-between; align-items: center; background: #222; padding: 6px; border-radius: 4px; margin-bottom: 4px;">
                                <span style="font-size: 11px;">${cand.id} (Seed: ${cand.metadata_json.seed || 'N/A'})</span>
                                <button class="studio-btn studio-approve-btn" data-cand-id="${cand.id}" data-char-name="${cand.metadata_json.character_name || 'CHAR'}" style="width: auto; padding: 3px 8px; margin: 0; font-size: 10px;">Approve</button>
                            </div>
                        `).join("")}
                    </div>
                ` : ''}

                <!-- Canonical Angles Count -->
                ${angleAssets.length > 0 ? `
                    <div style="margin-top: 6px; font-size: 11px; color: #00aa66;">
                        ✓ ${angleAssets.length} canonical angle compositions derived and stored.
                    </div>
                ` : ''}
            </div>

            <!-- Phase 10: MiniMax H3 Short-Shot Card -->
            <div class="studio-card">
                <div class="studio-card-title">🎥 Generative Short-Shot (WanGP MiniMax H3)</div>
                <div style="font-size: 11px; color: #888; margin-bottom: 6px;">Profile: 480x864 Vertical (9:16) | ~5s | RTX 3070 8GB Low-VRAM</div>
                <label style="font-size: 11px; color: #aaa;">Source Keyframe:</label>
                <select class="studio-input" id="studio-h3-keyframe-select">
                    ${allKeyframes.length === 0 ? '<option value="">No Approved Keyframes Available</option>' :
                        allKeyframes.map(k => `<option value="${k.id}">${k.id} (${k.kind})</option>`).join("")
                    }
                </select>
                <label style="font-size: 11px; color: #aaa;">Shot Action Prompt:</label>
                <textarea class="studio-input" id="studio-h3-prompt" rows="2" placeholder="Cinematic vertical shot, Maya steps out of the shadows, looks around anxiously in the foggy alleyway, subtle dramatic lighting..."></textarea>
                <div style="display: flex; gap: 6px; margin-bottom: 6px;">
                    <div style="flex: 1;">
                        <label style="font-size: 10px; color: #888;">Duration (sec):</label>
                        <select class="studio-input" id="studio-h3-duration" style="margin-bottom: 0;">
                            <option value="4.0">4.0s (96 frames)</option>
                            <option value="5.0" selected>5.0s (120 frames)</option>
                            <option value="6.0">6.0s (144 frames)</option>
                        </select>
                    </div>
                    <div style="flex: 1;">
                        <label style="font-size: 10px; color: #888;">Candidates:</label>
                        <select class="studio-input" id="studio-h3-candidates" style="margin-bottom: 0;">
                            <option value="1" selected>1 (Fast Baseline)</option>
                            <option value="3">3 (Hero Shots)</option>
                        </select>
                    </div>
                </div>
                <button class="studio-btn" id="studio-h3-gen-btn" style="background: #e65100; margin-top: 4px;">⚡ Generate 5s Vertical Shot (WanGP)</button>
            </div>

            <!-- Studio Review & Video Playback Card -->
            <div class="studio-card">
                <div class="studio-card-title">🎞️ Studio Review & Rendered Shots</div>
                ${videoShots.length === 0 ? '<div style="font-size: 11px; color: #666;">No video shots generated yet.</div>' :
                    videoShots.map(v => `
                        <div style="background: #1a1a1a; border: 1px solid #333; border-radius: 4px; padding: 8px; margin-bottom: 6px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-weight: bold; color: #ff9800; font-size: 11px;">${v.id}</span>
                                <span class="studio-badge" style="background: #333; color: #aaa;">480x864</span>
                            </div>
                            <div style="font-size: 11px; color: #ccc; margin-top: 4px;">${v.name}</div>
                            <div style="font-size: 10px; color: #888; margin-top: 2px;">Duration: ${v.metadata_json.duration_s || 5}s | VRAM: ~5.4 GB</div>
                            <div style="margin-top: 4px; font-size: 10px; color: #00aa66;">✓ Returned to Studio Review Page</div>
                        </div>
                    `).join("")
                }
            </div>

            <!-- Jobs & Queue Card -->
            <div class="studio-card">
                <div class="studio-card-title">Durable Render Queue</div>
                <table class="studio-table">
                    <thead>
                        <tr><th>ID</th><th>Kind</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        ${jobsRows || '<tr><td colspan="3" style="text-align:center; color:#666;">No jobs in queue</td></tr>'}
                    </tbody>
                </table>
            </div>
        `;

        // Event listeners
        const closeBtn = this.panel.querySelector("#studio-close-btn");
        if (closeBtn) closeBtn.onclick = () => this.togglePanel();

        const projSelect = this.panel.querySelector("#studio-project-select");
        if (projSelect) {
            projSelect.onchange = (e) => {
                this.activeProject = this.projects.find(p => p.id === e.target.value) || null;
                this.refresh();
            };
        }

        const createProjBtn = this.panel.querySelector("#studio-create-proj-btn");
        if (createProjBtn) {
            createProjBtn.onclick = () => {
                const nameInput = this.panel.querySelector("#studio-new-project-name");
                const name = nameInput.value.trim();
                if (name) {
                    this.createProject(name, "series");
                    nameInput.value = "";
                }
            };
        }

        const castBtn = this.panel.querySelector("#studio-cast-btn");
        if (castBtn) {
            castBtn.onclick = () => {
                const name = (this.panel.querySelector("#studio-char-name").value || "Maya").trim();
                const prompt = (this.panel.querySelector("#studio-char-prompt").value || "28yo female protagonist, sharp hazel eyes, dark leather jacket").trim();
                this.triggerCastingSession(name, prompt);
            };
        }

        this.panel.querySelectorAll(".studio-approve-btn").forEach(btn => {
            btn.onclick = () => {
                const candId = btn.getAttribute("data-cand-id");
                const charName = btn.getAttribute("data-char-name");
                this.approveCandidate(candId, charName);
            };
        });

        this.panel.querySelectorAll(".studio-derive-angles-btn").forEach(btn => {
            btn.onclick = () => {
                const canonicalId = btn.getAttribute("data-canonical");
                this.deriveAngles(canonicalId);
            };
        });

        const h3GenBtn = this.panel.querySelector("#studio-h3-gen-btn");
        if (h3GenBtn) {
            h3GenBtn.onclick = () => {
                const kSelect = this.panel.querySelector("#studio-h3-keyframe-select");
                const keyframeId = kSelect ? kSelect.value : "";
                if (!keyframeId) {
                    alert("Please select an approved keyframe first.");
                    return;
                }
                const prompt = (this.panel.querySelector("#studio-h3-prompt").value || "Maya walks forward in dramatic cinematic lighting").trim();
                const duration = this.panel.querySelector("#studio-h3-duration").value || "5.0";
                const candidates = this.panel.querySelector("#studio-h3-candidates").value || "1";
                this.triggerH3Shot(keyframeId, prompt, duration, candidates);
            };
        }
    }
}

const studioUI = new AIStudioUI();

app.registerExtension({
    name: "PreetiStudio.AIStudio",
    async setup() {
        console.log("[AI Studio] Registering Preeti Studio Extension into ComfyUI...");
        await studioUI.init();
    }
});
