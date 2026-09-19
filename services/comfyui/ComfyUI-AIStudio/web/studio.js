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
    async triggerSpecialistEdit(sourceAssetId, action, instruction) {
        if (!this.activeProject) {
            alert("Select or create an active project first.");
            return;
        }
        if (!sourceAssetId) {
            alert("Please select a source canonical asset to edit.");
            return;
        }
        try {
            const res = await fetch(`${STUDIO_API}/editor/edit`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: this.activeProject.id,
                    source_asset_id: sourceAssetId,
                    action: action,
                    instruction: instruction || null,
                    seed: Math.floor(Math.random() * 900000) + 100000
                })
            });
            if (res.ok) {
                const data = await res.json();
                alert(`Queued Qwen-Image-Edit [${action}] for ${sourceAssetId}! Job: ${data.edit_job_id}`);
                await this.refresh();
            } else {
                const err = await res.json();
                alert(`Edit request failed: ${err.detail || res.statusText}`);
            }
        } catch (e) {
            alert("Error queuing edit: " + e.message);
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

            <!-- Phase 5: Specialist Still Editor Card (Qwen-Image-Edit-2511 INT8) -->
            <div class="studio-card">
                <div class="studio-card-title">✨ Specialist Still Editor (Qwen-Image-Edit-2511 INT8)</div>
                <div style="font-size: 11px; color: #888; margin-bottom: 8px;">Targeted repair, outfit swap, prop correction & material swapping.</div>
                
                <label style="font-size: 11px; color: #aaa;">Source Character / Asset:</label>
                <select class="studio-input" id="studio-edit-source-select" style="margin-top: 2px;">
                    ${canonicalRefs.length === 0 ? '<option value="">No canonical assets available</option>' :
                        canonicalRefs.map(c => `<option value="${c.id}">${c.id} (${c.metadata_json.character_name || 'Character'})</option>`).join("")
                    }
                </select>

                <label style="font-size: 11px; color: #aaa;">Specialist Action:</label>
                <select class="studio-input" id="studio-edit-action-select" style="margin-top: 2px;">
                    <option value="preserve_identity_change_outfit">Preserve Identity & Change Outfit</option>
                    <option value="remove_unwanted_object">Remove Unwanted Object / Artifact</option>
                    <option value="repair_background">Repair Background Backdrop</option>
                    <option value="derive_angle">Derive Controlled Angle Perspective</option>
                    <option value="correct_prop">Correct / Replace Held Prop</option>
                    <option value="material_swap">Material & Surface Swap</option>
                </select>

                <label style="font-size: 11px; color: #aaa;">Custom Instruction (Optional):</label>
                <textarea class="studio-input" id="studio-edit-instruction" rows="2" placeholder="Leave blank to use action default, or provide custom direction..."></textarea>
                <button class="studio-btn" id="studio-trigger-edit-btn" style="background: #8b5cf6;">⚡ Run Specialist Edit</button>
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

        const triggerEditBtn = this.panel.querySelector("#studio-trigger-edit-btn");
        if (triggerEditBtn) {
            triggerEditBtn.onclick = () => {
                const sourceSelect = this.panel.querySelector("#studio-edit-source-select");
                const actionSelect = this.panel.querySelector("#studio-edit-action-select");
                const instructionText = this.panel.querySelector("#studio-edit-instruction");
                const sourceId = sourceSelect ? sourceSelect.value : null;
                const action = actionSelect ? actionSelect.value : "preserve_identity_change_outfit";
                const instruction = instructionText ? instructionText.value.trim() : "";
                this.triggerSpecialistEdit(sourceId, action, instruction);
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
