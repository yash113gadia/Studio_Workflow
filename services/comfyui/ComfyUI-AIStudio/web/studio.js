import { app } from "../../scripts/app.js";

const STUDIO_API = "http://127.0.0.1:8000/api/v1";

class AIStudioUI {
    constructor() {
        this.activeProject = null;
        this.projects = [];
        this.jobs = [];
        this.systemHealth = null;
        this.panel = null;
    }

    async init() {
        this.createSidebarUI();
        this.startPolling();
    }

    createSidebarUI() {
        // Create floating / sidebar toggle button on ComfyUI top menu
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

        // Create Panel Container
        this.panel = document.createElement("div");
        this.panel.id = "preeti-studio-panel";
        this.panel.className = "studio-sidebar-panel";
        this.panel.style.position = "fixed";
        this.panel.style.top = "0";
        this.panel.style.right = "0";
        this.panel.style.width = "380px";
        this.panel.style.height = "100vh";
        this.panel.style.zIndex = "1000";
        this.panel.style.boxShadow = "-4px 0 16px rgba(0,0,0,0.5)";
        this.panel.style.display = "none";

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

        try {
            const jRes = await fetch(`${STUDIO_API}/jobs?limit=10`);
            this.jobs = await jRes.json();
        } catch (e) {
            this.jobs = [];
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

    async enqueueDummyJob() {
        if (!this.activeProject) {
            alert("Please create or select a project first.");
            return;
        }
        try {
            const res = await fetch(`${STUDIO_API}/jobs`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: this.activeProject.id,
                    kind: "dummy",
                    priority: 50,
                    payload_json: { triggered_from_ui: true, timestamp: Date.now() }
                })
            });
            if (res.ok) {
                await this.refresh();
            }
        } catch (e) {
            alert("Error queuing job: " + e.message);
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

            <!-- Jobs & Queue Card -->
            <div class="studio-card">
                <div class="studio-card-title">Durable Render Queue</div>
                <div class="studio-status-row">
                    <span>Pending Jobs:</span>
                    <span class="studio-status-val">${this.systemHealth ? this.systemHealth.queue_pending_count : 0}</span>
                </div>
                <div class="studio-status-row">
                    <span>Running Jobs:</span>
                    <span class="studio-status-val">${this.systemHealth ? this.systemHealth.queue_running_count : 0}</span>
                </div>

                <table class="studio-table" style="margin-top: 8px;">
                    <thead>
                        <tr><th>ID</th><th>Kind</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        ${jobsRows || '<tr><td colspan="3" style="text-align:center; color:#666;">No jobs in queue</td></tr>'}
                    </tbody>
                </table>

                <button class="studio-btn" id="studio-queue-dummy-btn" style="margin-top: 10px;">+ Queue Dummy Job</button>
            </div>
        `;

        // Event listeners
        const closeBtn = this.panel.querySelector("#studio-close-btn");
        if (closeBtn) closeBtn.onclick = () => this.togglePanel();

        const projSelect = this.panel.querySelector("#studio-project-select");
        if (projSelect) {
            projSelect.onchange = (e) => {
                this.activeProject = this.projects.find(p => p.id === e.target.value) || null;
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

        const queueDummyBtn = this.panel.querySelector("#studio-queue-dummy-btn");
        if (queueDummyBtn) {
            queueDummyBtn.onclick = () => this.enqueueDummyJob();
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
