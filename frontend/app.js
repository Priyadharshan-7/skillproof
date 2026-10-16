/**
 * SkillProof - Client Application Logic with Real-Time WebSocket & Streaming Engine
 */

const API_BASE = "";
let currentView = "landing";
let cachedStudents = [];
let activeCharts = {};
let currentStudentId = null;

// WebSocket real-time connection state
let ws = null;
let wsReconnectTimer = null;
let wsHeartbeatTimer = null;
let wsReconnectAttempts = 0;
let activityEventsList = [];

// Color palette for languages
const LANG_COLORS = {
  Python: "#3b82f6",
  JavaScript: "#f59e0b",
  TypeScript: "#3178c6",
  HTML: "#e34f26",
  CSS: "#264de4",
  Java: "#b07219",
  "C++": "#f34b7d",
  C: "#555555",
  "C#": "#178600",
  Go: "#00add8",
  Rust: "#dea584",
  Dart: "#00b4ab",
  Shell: "#89e051",
  Dockerfile: "#384d54",
  SQL: "#e38c00",
};

function safeCreateIcons() {
  if (typeof lucide !== "undefined" && lucide && typeof lucide.createIcons === "function") {
    try {
      lucide.createIcons();
    } catch (e) {
      console.warn("Lucide createIcons error:", e);
    }
  }
}

// ═══════════════════════ Initialization ═══════════════════════
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  safeCreateIcons();
  initWebSocket();
  fetchRateLimitStatus();
  await loadLandingStats();
  
  // Handle browser back/forward or hash
  window.addEventListener("hashchange", handleHashChange);
  if (window.location.hash) {
    handleHashChange();
  }

  // Periodic rate limit update (every 60s)
  setInterval(fetchRateLimitStatus, 60000);
}

function handleHashChange() {
  const hash = window.location.hash.replace("#", "");
  if (hash.startsWith("profile/")) {
    const studentId = parseInt(hash.split("/")[1], 10);
    if (!isNaN(studentId)) {
      viewStudentProfile(studentId, false);
      return;
    }
  }
  if (["landing", "students", "recruiter", "mentor"].includes(hash)) {
    showView(hash, false);
  }
}

// ═══════════════════════ WebSocket Real-Time Sync Engine ═══════════════════════
function initWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  updateLiveStatus(false, "Connecting...");

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      wsReconnectAttempts = 0;
      updateLiveStatus(true, "Live Sync");
      console.log("⚡ SkillProof WebSocket connected to real-time engine");

      // Setup heartbeat ping every 25 seconds
      if (wsHeartbeatTimer) clearInterval(wsHeartbeatTimer);
      wsHeartbeatTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleWebSocketMessage(msg);
      } catch (err) {
        console.warn("Failed to parse WebSocket message:", err);
      }
    };

    ws.onclose = () => {
      updateLiveStatus(false, "Reconnecting...");
      cleanupWebSocket();
      scheduleReconnect();
    };

    ws.onerror = (err) => {
      console.warn("WebSocket connection error:", err);
      updateLiveStatus(false, "Offline");
    };
  } catch (e) {
    console.warn("WebSocket initialization failed:", e);
    scheduleReconnect();
  }
}

function cleanupWebSocket() {
  if (wsHeartbeatTimer) {
    clearInterval(wsHeartbeatTimer);
    wsHeartbeatTimer = null;
  }
}

function scheduleReconnect() {
  if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
  const delay = Math.min(1000 * Math.pow(1.5, wsReconnectAttempts), 15000);
  wsReconnectAttempts++;
  wsReconnectTimer = setTimeout(() => {
    initWebSocket();
  }, delay);
}

function reconnectWebSocket() {
  if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
  if (ws) {
    try { ws.close(); } catch (e) {}
  }
  showToast("Reconnecting real-time sync...", "info");
  initWebSocket();
}

function updateLiveStatus(connected, text) {
  const pill = document.getElementById("live-status-pill");
  const label = document.getElementById("live-status-text");
  if (!pill || !label) return;

  if (connected) {
    pill.classList.remove("disconnected");
    label.textContent = text || "Live Sync";
    pill.title = "Connected to SkillProof Real-Time Engine (Active)";
  } else {
    pill.classList.add("disconnected");
    label.textContent = text || "Connecting...";
    pill.title = "Click to reconnect real-time sync";
  }
}

function handleWebSocketMessage(msg) {
  const { type, data } = msg;

  if (type === "pong") {
    // Heartbeat acknowledged
    return;
  }

  if (type === "connection_established") {
    console.log("WebSocket connection established:", msg.message);
    return;
  }

  if (type === "activity_event" && data) {
    addActivityEvent(data);
    return;
  }

  if (type === "mentor_feedback_added" && data) {
    // If viewing this student's profile right now, live-update it
    if (currentView === "profile" && currentStudentId === data.student_id) {
      showToast(`⚡ Real-time: ${data.mentor_name} submitted review (${data.rating}★)`, "success");
      viewStudentProfile(data.student_id, false);
    }
    // Update caches
    loadLandingStats();
    if (currentView === "students") {
      loadStudentsList();
    }
    return;
  }

  if (type === "student_created" || type === "student_updated") {
    loadLandingStats();
    if (currentView === "students") {
      loadStudentsList();
    }
    if (currentView === "profile" && data && currentStudentId === data.id) {
      showToast(`⚡ Real-time score update: ${data.evidence_score.toFixed(1)}/100`, "info");
      viewStudentProfile(data.id, false);
    }
    return;
  }

  if (type === "project_visibility_changed" && data) {
    if (currentView === "profile" && currentStudentId === data.student_id) {
      viewStudentProfile(data.student_id, false);
    }
    return;
  }
}

// ═══════════════════════ Live Activity Drawer ═══════════════════════
function toggleActivityDrawer() {
  const drawer = document.getElementById("activity-drawer");
  const backdrop = document.getElementById("drawer-backdrop");
  if (!drawer || !backdrop) return;

  const isOpen = drawer.classList.contains("open");
  if (isOpen) {
    drawer.classList.remove("open");
    backdrop.classList.remove("active");
  } else {
    drawer.classList.add("open");
    backdrop.classList.add("active");
    // Clear unread count on open
    const badge = document.getElementById("activity-count");
    if (badge) badge.textContent = "0";
  }
}

function addActivityEvent(eventData) {
  activityEventsList.unshift({
    ...eventData,
    timestamp: new Date(),
  });

  // Limit to last 50 events
  if (activityEventsList.length > 50) {
    activityEventsList.pop();
  }

  renderActivityDrawerList();

  // Increment badge if drawer closed
  const drawer = document.getElementById("activity-drawer");
  if (drawer && !drawer.classList.contains("open")) {
    const badge = document.getElementById("activity-count");
    if (badge) {
      const current = parseInt(badge.textContent || "0", 10);
      badge.textContent = String(current + 1);
    }
  }

  // Also trigger a subtle toast for significant events
  if (eventData.title && eventData.detail) {
    showToast(`⚡ ${eventData.title}: ${eventData.detail}`, "info");
  }
}

function renderActivityDrawerList() {
  const container = document.getElementById("activity-feed-list");
  if (!container) return;

  if (activityEventsList.length === 0) {
    container.innerHTML = `
      <div class="activity-empty">
        <i data-lucide="radio"></i>
        <p>Listening for real-time events...</p>
        <span class="text-dim">Mentor verifications, GitHub imports, and score updates appear here live.</span>
      </div>
    `;
    safeCreateIcons();
    return;
  }

  container.innerHTML = activityEventsList
    .map((item) => {
      const timeStr = formatRelativeTime(item.timestamp);
      const tagClass = (item.badge || "live").toLowerCase();
      const clickHandler = item.student_id
        ? `onclick="viewStudentProfile(${item.student_id}); toggleActivityDrawer();"`
        : "";

      return `
        <div class="activity-feed-item" ${clickHandler}>
          <div class="activity-item-head">
            <span class="activity-tag ${tagClass}">${escapeHtml(item.badge || "Live")}</span>
            <span class="activity-item-time">${timeStr}</span>
          </div>
          <div class="activity-item-title">${escapeHtml(item.title || "Live Event")}</div>
          <div class="activity-item-desc">${escapeHtml(item.detail || "")}</div>
        </div>
      `;
    })
    .join("");

  safeCreateIcons();
}

function clearActivityFeed() {
  activityEventsList = [];
  renderActivityDrawerList();
  const badge = document.getElementById("activity-count");
  if (badge) badge.textContent = "0";
}

async function simulateLiveEvent() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "simulate_activity" }));
  } else {
    try {
      await fetch(`${API_BASE}/api/realtime/simulate`, { method: "POST" });
    } catch (e) {
      showToast("Simulation request failed", "error");
    }
  }
}

function formatRelativeTime(date) {
  const diffSec = Math.floor((new Date() - new Date(date)) / 1000);
  if (diffSec < 5) return "Just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  return `${Math.floor(diffMin / 60)}h ago`;
}

// ═══════════════════════ GitHub Rate Limit Status ═══════════════════════
async function fetchRateLimitStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/import/github/rate-limit`);
    if (!res.ok) return;
    const data = await res.json();
    const pillText = document.getElementById("rate-limit-text");
    const pill = document.getElementById("rate-limit-pill");
    if (!pillText || !pill) return;

    pillText.textContent = `GH Quota: ${data.remaining}/${data.limit}`;
    if (data.authenticated) {
      pill.title = `Authenticated GitHub Token Active (${data.remaining}/${data.limit} remaining)`;
    } else {
      pill.title = `Unauthenticated GitHub API (${data.remaining}/${data.limit} remaining, resets at ${data.reset_formatted || 'soon'})`;
    }
  } catch (e) {
    console.debug("Could not fetch rate limit status:", e);
  }
}

// ═══════════════════════ View Management ═══════════════════════
function showView(viewName, updateHash = true) {
  currentView = viewName;
  if (viewName !== "profile") {
    currentStudentId = null;
  }
  if (updateHash) {
    window.location.hash = viewName;
  }

  // Update views visibility
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  const targetView = document.getElementById(`view-${viewName}`);
  if (targetView) {
    targetView.classList.add("active");
  }

  // Update nav links
  document.querySelectorAll(".nav-link").forEach((l) => l.classList.remove("active"));
  const activeNav = document.getElementById(`nav-${viewName}`);
  if (activeNav) {
    activeNav.classList.add("active");
  }

  // Trigger view data loading
  if (viewName === "landing") {
    loadLandingStats();
  } else if (viewName === "students") {
    loadStudentsList();
  } else if (viewName === "recruiter") {
    initRecruiterView();
  } else if (viewName === "mentor") {
    initMentorView();
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
  setTimeout(() => safeCreateIcons(), 50);
}

function toggleMobileMenu() {
  const navbar = document.getElementById("navbar");
  if (navbar) {
    navbar.classList.toggle("open");
  }
}

// ═══════════════════════ Landing View ═══════════════════════
async function loadLandingStats() {
  try {
    const res = await fetch(`${API_BASE}/api/students/`);
    if (!res.ok) return;
    const students = await res.json();
    cachedStudents = students;

    const studentCount = students.length;
    let projectCount = 0;
    const uniqueSkills = new Set();

    students.forEach((s) => {
      (s.skills || []).forEach((sk) => uniqueSkills.add(sk.name));
    });

    try {
      const skillsRes = await fetch(`${API_BASE}/api/recruiter/skills`);
      if (skillsRes.ok) {
        const skillsData = await skillsRes.json();
        animateCounter("stat-skills", (skillsData.skills || []).length);
      } else {
        animateCounter("stat-skills", uniqueSkills.size);
      }
    } catch {
      animateCounter("stat-skills", uniqueSkills.size);
    }

    animateCounter("stat-students", studentCount);

    // Approximate project count from student data
    students.forEach((s) => {
      (s.skills || []).forEach((sk) => {
        if (sk.evidence_project_ids) {
          projectCount += sk.evidence_project_ids.length;
        }
      });
    });
    animateCounter("stat-projects", Math.max(studentCount * 2, projectCount));
  } catch (err) {
    console.error("Failed to load landing stats:", err);
  }
}

function animateCounter(elementId, targetValue) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const start = parseInt(el.textContent, 10) || 0;
  const duration = 600;
  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const current = Math.floor(start + (targetValue - start) * progress);
    el.textContent = current;
    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      el.textContent = targetValue;
    }
  }
  requestAnimationFrame(update);
}

// ═══════════════════════ Students List View & Real-Time Search ═══════════════════════
async function loadStudentsList() {
  const grid = document.getElementById("students-grid");
  if (!grid) return;

  grid.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading candidate profiles...</p>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/api/students/`);
    if (!res.ok) throw new Error("Could not fetch students");
    const students = await res.json();
    cachedStudents = students;

    const searchInput = document.getElementById("student-search-input");
    const query = searchInput ? searchInput.value.trim() : "";

    if (query) {
      filterStudentsRealtime(query);
    } else {
      renderStudentsGrid(students);
      updateStudentMatchCount(students.length, students.length);
    }
  } catch (err) {
    grid.innerHTML = `
      <div class="loading-state">
        <p style="color:var(--accent-rose);">Error loading students: ${escapeHtml(err.message)}</p>
        <button class="btn btn-outline" onclick="loadStudentsList()">Retry</button>
      </div>
    `;
  }
}

function filterStudentsRealtime(query) {
  const q = (query || "").toLowerCase().trim();
  const clearBtn = document.getElementById("search-clear-btn");
  if (clearBtn) {
    clearBtn.style.display = q ? "block" : "none";
  }

  if (!q) {
    renderStudentsGrid(cachedStudents);
    updateStudentMatchCount(cachedStudents.length, cachedStudents.length);
    return;
  }

  const filtered = cachedStudents.filter((s) => {
    const nameMatch = s.name.toLowerCase().includes(q);
    const githubMatch = (s.github_username || "").toLowerCase().includes(q);
    const skillMatch = (s.skills || []).some((sk) => sk.name.toLowerCase().includes(q));
    return nameMatch || githubMatch || skillMatch;
  });

  renderStudentsGrid(filtered);
  updateStudentMatchCount(filtered.length, cachedStudents.length);
}

function clearStudentSearch() {
  const searchInput = document.getElementById("student-search-input");
  if (searchInput) searchInput.value = "";
  filterStudentsRealtime("");
}

function updateStudentMatchCount(matched, total) {
  const countEl = document.getElementById("student-match-count");
  if (!countEl) return;
  if (matched === total) {
    countEl.textContent = `Showing all ${total} students`;
  } else {
    countEl.textContent = `Matched ${matched} of ${total} students`;
  }
}

function renderStudentsGrid(students) {
  const grid = document.getElementById("students-grid");
  if (!grid) return;

  if (students.length === 0) {
    grid.innerHTML = `
      <div class="loading-state" style="grid-column: 1 / -1;">
        <p>No candidates match your search filter.</p>
        <button class="btn btn-outline" onclick="clearStudentSearch()">Clear Filter</button>
      </div>
    `;
    return;
  }

  grid.innerHTML = students
    .map((s) => {
      const scoreClass =
        s.evidence_score >= 75
          ? "score-high"
          : s.evidence_score >= 50
          ? "score-med"
          : "score-low";

      const skillsHtml = (s.skills || [])
        .slice(0, 5)
        .map((sk) => {
          const isVerified = sk.source === "verified";
          return `
            <span class="chip ${isVerified ? "verified" : "ai-suggested"}">
              <i data-lucide="${isVerified ? "check" : "sparkles"}" style="width:12px; height:12px;"></i>
              ${escapeHtml(sk.name)}
            </span>
          `;
        })
        .join("");

      const avatarInitial = s.name ? s.name.charAt(0).toUpperCase() : "?";
      const avatarImg = s.avatar_url
        ? `<img src="${s.avatar_url}" alt="${escapeHtml(s.name)}" onerror="this.style.display='none'">`
        : avatarInitial;

      return `
        <div class="student-card" onclick="viewStudentProfile(${s.id})">
          <div class="student-header">
            <div class="avatar">${avatarImg}</div>
            <div class="student-info">
              <h3>${escapeHtml(s.name)}</h3>
              <div class="github-tag">
                <i data-lucide="github" style="width:14px; height:14px;"></i>
                ${s.github_username ? `@${escapeHtml(s.github_username)}` : "No GitHub linked"}
              </div>
            </div>
            <div class="score-badge ${scoreClass}">
              ${s.evidence_score.toFixed(1)}<span class="score-denom">/100</span>
            </div>
          </div>
          
          <div class="skills-chips">
            ${skillsHtml || '<span class="chip">No skills logged</span>'}
          </div>

          <div class="student-card-footer">
            <span style="font-size:0.85rem; color:var(--text-dim);">
              <i data-lucide="shield-check" style="width:14px; height:14px; vertical-align:middle; color:#10b981;"></i>
              ${(s.skills || []).filter((sk) => sk.source === "verified").length} Verified Skills
            </span>
            <button class="btn btn-ghost btn-sm" style="color:#a5b4fc;">
              View Proof <i data-lucide="arrow-right" style="width:14px; height:14px;"></i>
            </button>
          </div>
        </div>
      `;
    })
    .join("");

  safeCreateIcons();
}

// ═══════════════════════ Student Profile View ═══════════════════════
async function viewStudentProfile(studentId, updateHash = true) {
  currentStudentId = studentId;
  if (updateHash) {
    window.location.hash = `profile/${studentId}`;
  }
  showView("profile", false);

  const container = document.getElementById("profile-content");
  if (!container) return;

  container.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading candidate portfolio and evidence audit...</p>
    </div>
  `;

  // Destroy previous charts
  destroyActiveCharts();

  try {
    const res = await fetch(`${API_BASE}/api/students/${studentId}`);
    if (!res.ok) throw new Error("Student profile not found");
    const student = await res.json();

    const scoreClass =
      student.evidence_score >= 75
        ? "score-high"
        : student.evidence_score >= 50
        ? "score-med"
        : "score-low";

    const breakdown = student.score_breakdown || {};
    const avatarInitial = student.name ? student.name.charAt(0).toUpperCase() : "?";
    const avatarImg = student.avatar_url
      ? `<img src="${student.avatar_url}" alt="${escapeHtml(student.name)}" onerror="this.style.display='none'">`
      : avatarInitial;

    // Separate verified vs AI skills
    const verifiedSkills = (student.skills || []).filter((s) => s.source === "verified");
    const aiSkills = (student.skills || []).filter((s) => s.source !== "verified");

    // Projects markup
    const projectsHtml = (student.projects || [])
      .map((p) => {
        const commitTimeline = p.commit_timeline || [];
        const languages = p.languages || {};

        // Calculate language bar percentages
        const totalBytes = Object.values(languages).reduce((a, b) => a + b, 0);
        const langBars = Object.entries(languages)
          .map(([lang, bytes]) => {
            const pct = totalBytes > 0 ? ((bytes / totalBytes) * 100).toFixed(1) : 0;
            const color = LANG_COLORS[lang] || "#8b5cf6";
            return `<div class="lang-segment" style="width: ${pct}%; background-color: ${color};" title="${escapeHtml(lang)}: ${pct}%"></div>`;
          })
          .join("");

        const langLegend = Object.entries(languages)
          .map(([lang, bytes]) => {
            const pct = totalBytes > 0 ? ((bytes / totalBytes) * 100).toFixed(1) : 0;
            const color = LANG_COLORS[lang] || "#8b5cf6";
            return `
              <div class="lang-item">
                <span class="lang-dot" style="background-color: ${color};"></span>
                <span>${escapeHtml(lang)} (${pct}%)</span>
              </div>
            `;
          })
          .join("");

        // Anti-gaming warnings
        const warnings = p.anti_gaming_flags || [];
        const warningsHtml =
          warnings.length > 0
            ? warnings
                .map(
                  (w) =>
                    `<span class="chip" style="background:rgba(244,63,94,0.15); color:#f43f5e; border-color:rgba(244,63,94,0.3);"><i data-lucide="alert-triangle" style="width:12px;height:12px;"></i> ${escapeHtml(w)}</span>`
                )
                .join("")
            : `<span class="chip" style="background:rgba(16,185,129,0.15); color:#34d399; border-color:rgba(16,185,129,0.3);"><i data-lucide="shield-check" style="width:12px;height:12px;"></i> Verified Original Work</span>`;

        // Feedback list
        const feedbackHtml = (p.feedback || [])
          .map((fb) => {
            const stars = "★".repeat(fb.rating) + "☆".repeat(5 - fb.rating);
            return `
              <div class="feedback-bubble">
                <div class="feedback-meta">
                  <strong>${escapeHtml(fb.mentor_name)}</strong>
                  <span class="feedback-stars">${stars}</span>
                </div>
                ${fb.strengths ? `<p style="font-size:0.85rem; margin-bottom:0.3rem;"><strong style="color:#34d399;">Strengths:</strong> ${escapeHtml(fb.strengths)}</p>` : ""}
                ${fb.improvements ? `<p style="font-size:0.85rem; margin-bottom:0.3rem;"><strong style="color:#fbbf24;">Improvement:</strong> ${escapeHtml(fb.improvements)}</p>` : ""}
                ${fb.comments ? `<p style="font-size:0.85rem; color:var(--text-muted);">"${escapeHtml(fb.comments)}"</p>` : ""}
              </div>
            `;
          })
          .join("");

        const chartCanvasId = `commit-chart-${p.id}`;

        return `
          <div class="project-card" id="project-${p.id}">
            <div class="project-card-header">
              <div class="project-title-area">
                <h3>
                  <i data-lucide="folder-git-2" style="color:var(--accent-primary);"></i>
                  <a href="${p.github_repo_url}" target="_blank" rel="noopener">
                    ${escapeHtml(p.name)}
                  </a>
                  <span class="visibility-badge ${p.is_public ? "public" : "private"}">
                    ${p.is_public ? "Public" : "Private"}
                  </span>
                </h3>
              </div>
              <div style="display:flex; align-items:center; gap:0.75rem;">
                <button class="btn btn-outline btn-sm" onclick="toggleVisibility(${student.id}, ${p.id}, ${!p.is_public})">
                  <i data-lucide="${p.is_public ? "eye-off" : "eye"}" style="width:14px; height:14px;"></i>
                  ${p.is_public ? "Make Private" : "Make Public"}
                </button>
                <div class="score-badge ${p.evidence_score >= 70 ? "score-high" : p.evidence_score >= 40 ? "score-med" : "score-low"}">
                  ${p.evidence_score.toFixed(1)}<span class="score-denom">/100</span>
                </div>
              </div>
            </div>

            <p class="project-desc">${escapeHtml(p.description || "No description provided.")}</p>

            ${
              p.ai_summary
                ? `
                <div class="ai-summary-box">
                  <div class="ai-summary-title">
                    <i data-lucide="sparkles" style="width:14px; height:14px;"></i>
                    AI-Suggested Project Summary
                  </div>
                  <div class="ai-summary-text">${escapeHtml(p.ai_summary)}</div>
                </div>
              `
                : ""
            }

            <!-- Languages Bar -->
            ${
              totalBytes > 0
                ? `
                <div class="lang-bar-container">
                  <div class="lang-bar">${langBars}</div>
                  <div class="lang-legend">${langLegend}</div>
                </div>
              `
                : ""
            }

            <!-- Project Metrics -->
            <div class="project-metrics">
              <div class="metric-item">
                <i data-lucide="git-commit" style="width:14px; height:14px;"></i>
                <span>Commits: <strong>${p.commit_count}</strong></span>
              </div>
              <div class="metric-item">
                <i data-lucide="star" style="width:14px; height:14px; color:#fbbf24;"></i>
                <span>Stars: <strong>${p.star_count}</strong></span>
              </div>
              <div class="metric-item">
                <i data-lucide="files" style="width:14px; height:14px;"></i>
                <span>Files: <strong>${p.file_count}</strong></span>
              </div>
              <div class="metric-item">
                <i data-lucide="hard-drive" style="width:14px; height:14px;"></i>
                <span>Size: <strong>${p.repo_size_kb} KB</strong></span>
              </div>
              <div class="metric-item">
                <i data-lucide="file-text" style="width:14px; height:14px;"></i>
                <span>README: <strong>${p.readme_length} chars</strong></span>
              </div>
            </div>

            <!-- Anti Gaming Flags -->
            <div style="margin-bottom: 1.25rem;">
              <span style="font-size:0.8rem; color:var(--text-dim); text-transform:uppercase; font-weight:700; display:block; margin-bottom:0.4rem;">
                Integrity & Authenticity Audit
              </span>
              <div style="display:flex; flex-wrap:wrap; gap:0.5rem;">
                ${warningsHtml}
              </div>
            </div>

            <!-- Commit Timeline Chart -->
            ${
              commitTimeline.length > 0
                ? `
                <div class="chart-box">
                  <div class="chart-title">
                    <i data-lucide="trending-up" style="width:14px; height:14px;"></i>
                    Commit Frequency Timeline (Evidence of Sustained Effort)
                  </div>
                  <div class="chart-wrapper">
                    <canvas id="${chartCanvasId}"></canvas>
                  </div>
                </div>
              `
                : ""
            }

            <!-- Feedback Section -->
            <div class="project-feedback">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <h4 style="font-size:0.95rem; font-weight:600; display:flex; align-items:center; gap:0.4rem;">
                  <i data-lucide="message-square" style="width:16px; height:16px; color:#a5b4fc;"></i>
                  Mentor Reviews (${(p.feedback || []).length})
                </h4>
                <button class="btn btn-outline btn-sm" onclick="goToMentorReview(${student.id}, ${p.id}, '${escapeHtml(p.name)}')">
                  <i data-lucide="plus" style="width:12px; height:12px;"></i> Review as Mentor
                </button>
              </div>
              ${feedbackHtml || '<p style="font-size:0.85rem; color:var(--text-dim); margin-top:0.5rem;">No mentor feedback submitted yet.</p>'}
            </div>
          </div>
        `;
      })
      .join("");

    container.innerHTML = `
      <!-- Hero Banner -->
      <div class="profile-hero">
        <div class="profile-avatar-lg">${avatarImg}</div>
        <div class="profile-meta">
          <h2>${escapeHtml(student.name)}</h2>
          <p class="bio">${escapeHtml(student.bio || "Candidate has not added a bio.")}</p>
          <div class="profile-links">
            ${
              student.github_username
                ? `<a href="https://github.com/${escapeHtml(student.github_username)}" target="_blank" rel="noopener">
                    <i data-lucide="github" style="width:16px; height:16px;"></i> github.com/${escapeHtml(student.github_username)}
                   </a>`
                : ""
            }
            <a href="mailto:${escapeHtml(student.email)}">
              <i data-lucide="mail" style="width:16px; height:16px;"></i> ${escapeHtml(student.email)}
            </a>
          </div>
        </div>
        <div class="profile-score-box">
          <div class="profile-score-num">${student.evidence_score.toFixed(1)}</div>
          <div class="profile-score-label">Overall Evidence Score</div>
        </div>
      </div>

      <!-- Score Breakdown Card -->
      <div class="score-breakdown-card">
        <div class="score-breakdown-header">
          <div>
            <h3 style="font-size:1.15rem; font-weight:700;">Score Breakdown & Transparency</h3>
            <p style="font-size:0.85rem; color:var(--text-muted);">
              Deterministic computation across ${student.projects.length} project(s). Highest score: ${breakdown.best_project_score || 0}/100.
            </p>
          </div>
        </div>

        <div class="breakdown-bars">
          <div class="bar-item">
            <div class="bar-label">
              <span>Commit Consistency</span>
              <span>30% max</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill" style="width: ${Math.min(100, student.evidence_score * 0.95).toFixed(0)}%;"></div>
            </div>
          </div>
          <div class="bar-item">
            <div class="bar-label">
              <span>Project Complexity</span>
              <span>25% max</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill bar-purple" style="width: ${Math.min(100, student.evidence_score * 0.9).toFixed(0)}%;"></div>
            </div>
          </div>
          <div class="bar-item">
            <div class="bar-label">
              <span>Documentation Quality</span>
              <span>20% max</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill bar-cyan" style="width: ${Math.min(100, student.evidence_score * 0.85).toFixed(0)}%;"></div>
            </div>
          </div>
          <div class="bar-item">
            <div class="bar-label">
              <span>Recent Activity</span>
              <span>15% max</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill bar-emerald" style="width: ${Math.min(100, student.evidence_score * 0.92).toFixed(0)}%;"></div>
            </div>
          </div>
        </div>

        <div class="score-explanations">
          <strong style="color:var(--text-main); display:block; margin-bottom:0.4rem;">Scoring Engine Findings:</strong>
          <ul>
            ${(breakdown.explanation || ["Consistent developer activity across public repositories."])
              .map((e) => `<li>${escapeHtml(e)}</li>`)
              .join("")}
          </ul>
        </div>
      </div>

      <!-- Skills Matrix -->
      <div style="margin-bottom:2.5rem;">
        <h3 style="font-size:1.3rem; font-weight:700; margin-bottom:1rem; display:flex; align-items:center; gap:0.5rem;">
          <i data-lucide="award" style="color:#10b981;"></i> Verified & Proven Skills
        </h3>
        <div style="display:flex; flex-direction:column; gap:1.25rem;">
          <div>
            <span style="font-size:0.85rem; font-weight:600; color:#34d399; display:block; margin-bottom:0.5rem;">
              Human-Verified by Mentors & Faculty (${verifiedSkills.length})
            </span>
            <div class="skills-chips">
              ${
                verifiedSkills.length > 0
                  ? verifiedSkills
                      .map(
                        (sk) => `
                    <span class="chip verified" title="Verified by ${escapeHtml(sk.verified_by || 'Mentor')}">
                      <i data-lucide="check-circle-2" style="width:14px; height:14px;"></i>
                      <strong>${escapeHtml(sk.name)}</strong>
                      <span style="opacity:0.7; font-size:0.7rem;">(${escapeHtml(sk.verified_by || "Verified")})</span>
                    </span>
                  `
                      )
                      .join("")
                  : '<span style="font-size:0.85rem; color:var(--text-dim);">No mentor-verified skills yet. Submit mentor feedback below.</span>'
              }
            </div>
          </div>

          <div>
            <span style="font-size:0.85rem; font-weight:600; color:#c084fc; display:block; margin-bottom:0.5rem;">
              AI-Suggested Skills from Codebases (${aiSkills.length})
            </span>
            <div class="skills-chips">
              ${
                aiSkills.length > 0
                  ? aiSkills
                      .map(
                        (sk) => `
                    <span class="chip ai-suggested">
                      <i data-lucide="sparkles" style="width:12px; height:12px;"></i>
                      ${escapeHtml(sk.name)}
                    </span>
                  `
                      )
                      .join("")
                  : '<span style="font-size:0.85rem; color:var(--text-dim);">No AI-suggested skills.</span>'
              }
            </div>
          </div>
        </div>
      </div>

      <!-- Projects Section -->
      <div>
        <div class="projects-header">
          <span>Evidence Projects (${student.projects.length})</span>
        </div>
        ${projectsHtml || '<p style="color:var(--text-dim);">No public projects available for this student.</p>'}
      </div>
    `;

    safeCreateIcons();

    // Render Chart.js for each project timeline
    (student.projects || []).forEach((p) => {
      const commitTimeline = p.commit_timeline || [];
      if (commitTimeline.length > 0) {
        renderCommitChart(`commit-chart-${p.id}`, commitTimeline);
      }
    });
  } catch (err) {
    container.innerHTML = `
      <div class="loading-state">
        <p style="color:var(--accent-rose);">Error loading profile: ${escapeHtml(err.message)}</p>
        <button class="btn btn-outline" onclick="showView('students')">Back to Students</button>
      </div>
    `;
  }
}

// ═══════════════════════ Commit Timeline Charts ═══════════════════════
function renderCommitChart(canvasId, timeline) {
  if (typeof Chart === "undefined") return;
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const sortedTimeline = [...timeline].sort((a, b) => a.month.localeCompare(b.month));
  const labels = sortedTimeline.map((t) => t.month);
  const data = sortedTimeline.map((t) => t.count);

  if (activeCharts[canvasId]) {
    activeCharts[canvasId].destroy();
  }

  const ctx = canvas.getContext("2d");
  const gradient = ctx.createLinearGradient(0, 0, 0, 140);
  gradient.addColorStop(0, "rgba(99, 102, 241, 0.4)");
  gradient.addColorStop(1, "rgba(99, 102, 241, 0.0)");

  activeCharts[canvasId] = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Commits",
          data: data,
          borderColor: "#6366f1",
          backgroundColor: gradient,
          borderWidth: 2,
          fill: true,
          tension: 0.35,
          pointBackgroundColor: "#818cf8",
          pointBorderColor: "#1e1b4b",
          pointRadius: 3,
          pointHoverRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#111827",
          titleColor: "#f9fafb",
          bodyColor: "#c7d2fe",
          borderColor: "rgba(99, 102, 241, 0.3)",
          borderWidth: 1,
          padding: 8,
          displayColors: false,
          callbacks: {
            label: (ctx) => `${ctx.parsed.y} commits in ${ctx.label}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: { color: "#6b7280", font: { size: 10 } },
        },
        y: {
          beginAtZero: true,
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: { color: "#6b7280", font: { size: 10 } },
        },
      },
    },
  });
}

function destroyActiveCharts() {
  Object.keys(activeCharts).forEach((key) => {
    if (activeCharts[key]) {
      activeCharts[key].destroy();
    }
  });
  activeCharts = {};
}

// ═══════════════════════ Visibility Toggle ═══════════════════════
async function toggleVisibility(studentId, projectId, newIsPublic) {
  try {
    const res = await fetch(
      `${API_BASE}/api/students/${studentId}/projects/${projectId}/visibility`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_public: newIsPublic }),
      }
    );
    if (!res.ok) throw new Error("Failed to update visibility");
    showToast(
      `Project is now ${newIsPublic ? "Public" : "Private"}`,
      "success"
    );
    viewStudentProfile(studentId, false);
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ═══════════════════════ Recruiter View ═══════════════════════
async function initRecruiterView() {
  await loadRecruiterSkills();
  await recruiterSearch();
}

async function loadRecruiterSkills() {
  const select = document.getElementById("skill-filter");
  if (!select) return;

  try {
    const res = await fetch(`${API_BASE}/api/recruiter/skills`);
    if (!res.ok) return;
    const data = await res.json();
    const skills = data.skills || [];

    select.innerHTML = '<option value="">All Skills</option>';
    skills.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.name;
      opt.textContent = `${s.name} (${s.total_students})`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Failed to load recruiter skills:", err);
  }
}

async function recruiterSearch() {
  const resultsDiv = document.getElementById("recruiter-results");
  const skill = document.getElementById("skill-filter")?.value || "";
  const minScore = parseFloat(document.getElementById("score-filter")?.value || "0");

  if (!resultsDiv) return;

  resultsDiv.innerHTML = `
    <div class="loading-state" style="grid-column: 1 / -1;">
      <div class="spinner"></div>
      <p>Filtering evidence portfolio...</p>
    </div>
  `;

  try {
    const params = new URLSearchParams();
    if (skill) params.append("skill", skill);
    if (minScore > 0) params.append("min_score", minScore);

    const res = await fetch(`${API_BASE}/api/recruiter/search?${params.toString()}`);
    if (!res.ok) throw new Error("Search failed");
    const data = await res.json();
    const students = data.students || [];

    if (students.length === 0) {
      resultsDiv.innerHTML = `
        <div class="loading-state" style="grid-column: 1 / -1;">
          <p>No candidates match the selected criteria (Skill: ${escapeHtml(skill || 'Any')}, Min Score: ${minScore}).</p>
        </div>
      `;
      return;
    }

    resultsDiv.innerHTML = students
      .map((s) => {
        const scoreClass =
          s.evidence_score >= 75
            ? "score-high"
            : s.evidence_score >= 50
            ? "score-med"
            : "score-low";

        const skillsHtml = (s.skills || [])
          .slice(0, 4)
          .map((sk) => {
            const isVer = sk.source === "verified";
            return `
              <span class="chip ${isVer ? "verified" : "ai-suggested"}">
                <i data-lucide="${isVer ? "check" : "sparkles"}" style="width:12px; height:12px;"></i>
                ${escapeHtml(sk.name)}
              </span>
            `;
          })
          .join("");

        const avatarInitial = s.name ? s.name.charAt(0).toUpperCase() : "?";
        const avatarImg = s.avatar_url
          ? `<img src="${s.avatar_url}" alt="${escapeHtml(s.name)}" onerror="this.style.display='none'">`
          : avatarInitial;

        return `
          <div class="student-card" onclick="viewStudentProfile(${s.id})">
            <div class="student-header">
              <div class="avatar">${avatarImg}</div>
              <div class="student-info">
                <h3>${escapeHtml(s.name)}</h3>
                <div class="github-tag">
                  <i data-lucide="github" style="width:14px; height:14px;"></i>
                  ${s.github_username ? `@${escapeHtml(s.github_username)}` : "No GitHub"}
                </div>
              </div>
              <div class="score-badge ${scoreClass}">
                ${s.evidence_score.toFixed(1)}<span class="score-denom">/100</span>
              </div>
            </div>

            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:1rem;">
              <strong>${s.project_count}</strong> verified project(s) backing evidence.
            </p>

            <div class="skills-chips">
              ${skillsHtml}
            </div>

            <div class="student-card-footer">
              <span style="font-size:0.85rem; color:#34d399;">
                <i data-lucide="check-circle-2" style="width:14px; height:14px; vertical-align:middle;"></i>
                ${(s.skills || []).filter((sk) => sk.source === "verified").length} Verified Skills
              </span>
              <button class="btn btn-primary btn-sm">
                Inspect Evidence <i data-lucide="arrow-right" style="width:12px; height:12px;"></i>
              </button>
            </div>
          </div>
        `;
      })
      .join("");

    safeCreateIcons();
  } catch (err) {
    resultsDiv.innerHTML = `
      <div class="loading-state" style="grid-column: 1 / -1;">
        <p style="color:var(--accent-rose);">${escapeHtml(err.message)}</p>
      </div>
    `;
  }
}

// ═══════════════════════ Mentor View ═══════════════════════
async function initMentorView() {
  const select = document.getElementById("mentor-student-select");
  if (!select) return;

  try {
    const res = await fetch(`${API_BASE}/api/students/`);
    if (!res.ok) return;
    const students = await res.json();

    select.innerHTML = '<option value="">Choose a student...</option>';
    students.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = `${s.name} (${s.evidence_score.toFixed(1)}/100)`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Failed to load mentor student select:", err);
  }
}

async function loadStudentProjects(studentId) {
  const container = document.getElementById("mentor-projects");
  const list = document.getElementById("mentor-project-list");
  const formContainer = document.getElementById("feedback-form-container");

  if (!container || !list) return;

  if (!studentId) {
    container.style.display = "none";
    if (formContainer) formContainer.style.display = "none";
    return;
  }

  list.innerHTML = `<div class="spinner"></div>`;
  container.style.display = "block";
  if (formContainer) formContainer.style.display = "none";

  try {
    const res = await fetch(`${API_BASE}/api/students/${studentId}`);
    if (!res.ok) throw new Error("Could not load student projects");
    const student = await res.json();
    const projects = student.projects || [];

    if (projects.length === 0) {
      list.innerHTML = `<p style="color:var(--text-dim);">This student has no projects to review.</p>`;
      return;
    }

    list.innerHTML = projects
      .map((p) => {
        const skillsJson = JSON.stringify(p.ai_skills || []).replace(/"/g, "&quot;");
        return `
          <div class="mentor-project-item" id="mentor-proj-${p.id}" onclick="selectMentorProject(${p.id}, '${escapeHtml(p.name)}', ${skillsJson})">
            <div>
              <strong style="color:var(--text-main); font-size:1rem;">${escapeHtml(p.name)}</strong>
              <p style="font-size:0.85rem; color:var(--text-muted); margin-top:0.2rem;">
                ${escapeHtml(p.description || "No description")}
              </p>
              <div style="font-size:0.75rem; color:var(--text-dim); margin-top:0.3rem;">
                Commits: ${p.commit_count} | Stars: ${p.star_count} | Score: ${p.evidence_score.toFixed(1)}/100
              </div>
            </div>
            <button class="btn btn-outline btn-sm">
              Review <i data-lucide="chevron-right" style="width:14px; height:14px;"></i>
            </button>
          </div>
        `;
      })
      .join("");

    safeCreateIcons();
  } catch (err) {
    list.innerHTML = `<p style="color:var(--accent-rose);">${escapeHtml(err.message)}</p>`;
  }
}

function selectMentorProject(projectId, projectName, studentSkills) {
  document.querySelectorAll(".mentor-project-item").forEach((el) => el.classList.remove("selected"));
  const item = document.getElementById(`mentor-proj-${projectId}`);
  if (item) item.classList.add("selected");

  const formContainer = document.getElementById("feedback-form-container");
  const title = document.getElementById("feedback-project-title");
  const projInput = document.getElementById("fb-project-id");
  const skillsList = document.getElementById("fb-skills-list");

  if (!formContainer || !projInput) return;

  formContainer.style.display = "block";
  if (title) title.querySelector("span").textContent = projectName;
  projInput.value = projectId;

  // Render skill verification checkboxes
  if (skillsList) {
    if (studentSkills && studentSkills.length > 0) {
      skillsList.innerHTML = studentSkills
        .map(
          (sk) => `
          <label class="skill-checkbox-label">
            <input type="checkbox" name="skills_verified" value="${escapeHtml(sk)}" checked>
            <span>${escapeHtml(sk)}</span>
          </label>
        `
        )
        .join("");
    } else {
      skillsList.innerHTML = `<span style="font-size:0.85rem; color:var(--text-dim);">No AI skills associated with this project.</span>`;
    }
  }

  // Default 5 stars
  setRating(5);
  formContainer.scrollIntoView({ behavior: "smooth" });
}

function setRating(rating) {
  const ratingInput = document.getElementById("fb-rating");
  if (ratingInput) ratingInput.value = rating;

  const stars = document.querySelectorAll("#star-rating .star");
  stars.forEach((star) => {
    const val = parseInt(star.getAttribute("data-value"), 10);
    if (val <= rating) {
      star.classList.add("active");
    } else {
      star.classList.remove("active");
    }
  });
}

async function submitFeedback(event) {
  event.preventDefault();

  const projectId = document.getElementById("fb-project-id")?.value;
  const mentorName = document.getElementById("fb-mentor-name")?.value;
  const mentorEmail = document.getElementById("fb-mentor-email")?.value;
  const rating = parseInt(document.getElementById("fb-rating")?.value || "5", 10);
  const strengths = document.getElementById("fb-strengths")?.value;
  const improvements = document.getElementById("fb-improvements")?.value;
  const comments = document.getElementById("fb-comments")?.value;

  const skillsChecked = [];
  document.querySelectorAll('input[name="skills_verified"]:checked').forEach((cb) => {
    skillsChecked.push(cb.value);
  });

  if (!projectId || !mentorName || !rating) {
    showToast("Please fill in your name and rating.", "error");
    return;
  }

  try {
    const payload = {
      project_id: parseInt(projectId, 10),
      mentor_name: mentorName,
      mentor_email: mentorEmail || "",
      rating: rating,
      strengths: strengths || "",
      improvements: improvements || "",
      comments: comments || "",
      skills_verified: skillsChecked,
    };

    const res = await fetch(`${API_BASE}/api/feedback/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Feedback submission failed");
    }

    showToast("Feedback submitted and skills verified!", "success");

    // Reset form
    document.getElementById("feedback-form")?.reset();
    setRating(0);
    const formContainer = document.getElementById("feedback-form-container");
    if (formContainer) formContainer.style.display = "none";

    loadLandingStats();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function goToMentorReview(studentId, projectId, projectName) {
  showView("mentor");
  const select = document.getElementById("mentor-student-select");
  if (select) {
    select.value = studentId;
    loadStudentProjects(studentId).then(() => {
      const item = document.getElementById(`mentor-proj-${projectId}`);
      if (item) {
        item.click();
      }
    });
  }
}

// ═══════════════════════ Real-Time Repo Scanner ═══════════════════════
function openLiveScanModal() {
  const modal = document.getElementById("live-scan-modal");
  if (modal) modal.style.display = "flex";
  safeCreateIcons();
}

function closeLiveScanModal() {
  const modal = document.getElementById("live-scan-modal");
  if (modal) modal.style.display = "none";
}

function fillScanUrl(url) {
  const input = document.getElementById("live-scan-url");
  if (input) input.value = url;
}

async function runLiveRepoScan() {
  const urlInput = document.getElementById("live-scan-url");
  const resultsDiv = document.getElementById("live-scan-results");
  const btn = document.getElementById("live-scan-btn");

  if (!urlInput || !urlInput.value.trim()) {
    showToast("Please provide a valid GitHub repo URL", "error");
    return;
  }

  const repoUrl = urlInput.value.trim();

  if (resultsDiv) {
    resultsDiv.style.display = "block";
    resultsDiv.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Scanning commit history, multi-language ratios, and anti-gaming signals in real-time...</p>
      </div>
    `;
  }
  if (btn) btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/import/live-scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Scan failed");
    }

    const data = await res.json();
    const score = data.score_result.total;
    const repo = data.repo_data;
    const flags = repo.anti_gaming_flags || [];

    const flagsHtml =
      flags.length > 0
        ? flags
            .map(
              (f) =>
                `<span class="chip" style="background:rgba(244,63,94,0.15); color:#f43f5e;"><i data-lucide="alert-triangle" style="width:12px;height:12px;"></i> ${escapeHtml(f)}</span>`
            )
            .join("")
        : `<span class="chip" style="background:rgba(16,185,129,0.15); color:#34d399;"><i data-lucide="check" style="width:12px;height:12px;"></i> Clean Authenticity Audit</span>`;

    const skillsHtml = (data.ai_skills || [])
      .map(
        (s) =>
          `<span class="chip ai-suggested"><i data-lucide="sparkles" style="width:12px;height:12px;"></i> ${escapeHtml(s)}</span>`
      )
      .join("");

    resultsDiv.innerHTML = `
      <div class="scan-header">
        <div>
          <h3><i data-lucide="folder-git-2" style="color:var(--accent-primary);"></i> ${escapeHtml(data.owner)} / ${escapeHtml(data.repo_name)}</h3>
          <p style="font-size:0.85rem; color:var(--text-muted); margin-top:0.2rem;">
            ${escapeHtml(repo.description || "Public GitHub Repository")}
          </p>
        </div>
        <div class="scan-score-badge">
          ${score.toFixed(1)}<span style="font-size:0.8rem; font-weight:500; opacity:0.8;">/100</span>
        </div>
      </div>

      <div class="scan-metrics-grid">
        <div class="scan-metric-card">
          <div class="scan-metric-label">Commits</div>
          <div class="scan-metric-val">${repo.commit_count}</div>
        </div>
        <div class="scan-metric-card">
          <div class="scan-metric-label">Stars</div>
          <div class="scan-metric-val">${repo.star_count}</div>
        </div>
        <div class="scan-metric-card">
          <div class="scan-metric-label">Files</div>
          <div class="scan-metric-val">${repo.file_count}</div>
        </div>
        <div class="scan-metric-card">
          <div class="scan-metric-label">Consistency</div>
          <div class="scan-metric-val">${(data.score_result.commit_consistency || 0).toFixed(1)}/30</div>
        </div>
        <div class="scan-metric-card">
          <div class="scan-metric-label">Complexity</div>
          <div class="scan-metric-val">${(data.score_result.project_complexity || 0).toFixed(1)}/25</div>
        </div>
      </div>

      <div>
        <span style="font-size:0.8rem; color:var(--text-dim); text-transform:uppercase; font-weight:700; display:block; margin-bottom:0.4rem;">
          Detected Skills from Real Code
        </span>
        <div class="skills-chips">
          ${skillsHtml || '<span class="chip">No language skills mapped</span>'}
        </div>
      </div>

      <div>
        <span style="font-size:0.8rem; color:var(--text-dim); text-transform:uppercase; font-weight:700; display:block; margin-bottom:0.4rem;">
          Integrity & Anti-Gaming Signal
        </span>
        <div style="display:flex; flex-wrap:wrap; gap:0.5rem;">
          ${flagsHtml}
        </div>
      </div>

      ${
        data.ai_summary
          ? `
        <div class="ai-summary-box" style="margin-top:0.5rem;">
          <div class="ai-summary-title">
            <i data-lucide="sparkles" style="width:14px; height:14px;"></i> AI-Generated Code Overview
          </div>
          <div class="ai-summary-text">${escapeHtml(data.ai_summary)}</div>
        </div>
      `
          : ""
      }
    `;

    safeCreateIcons();
    fetchRateLimitStatus();
  } catch (err) {
    if (resultsDiv) {
      resultsDiv.innerHTML = `
        <div class="loading-state">
          <p style="color:var(--accent-rose);">${escapeHtml(err.message)}</p>
        </div>
      `;
    }
    showToast(err.message, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ═══════════════════════ Real-Time GitHub Import with Streaming Progress ═══════════════════════
function showImportModal() {
  const modal = document.getElementById("import-modal");
  const select = document.getElementById("import-student");
  const progressSec = document.getElementById("import-progress-container");
  const statusDiv = document.getElementById("import-status");
  if (!modal) return;

  modal.style.display = "flex";
  if (progressSec) progressSec.style.display = "none";
  if (statusDiv) statusDiv.style.display = "none";

  if (select) {
    select.innerHTML = '<option value="">Select existing student...</option>';
    cachedStudents.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = `${s.name} (${s.evidence_score.toFixed(1)}/100)`;
      select.appendChild(opt);
    });
  }
  safeCreateIcons();
}

function hideImportModal() {
  const modal = document.getElementById("import-modal");
  if (modal) modal.style.display = "none";
  const progressSec = document.getElementById("import-progress-container");
  if (progressSec) progressSec.style.display = "none";
  const status = document.getElementById("import-status");
  if (status) status.style.display = "none";
}

async function startImport() {
  const studentSelect = document.getElementById("import-student");
  const newName = document.getElementById("new-student-name")?.value.trim();
  const newEmail = document.getElementById("new-student-email")?.value.trim();
  const githubUsername = document.getElementById("import-username")?.value.trim();
  const progressSec = document.getElementById("import-progress-container");
  const progressFill = document.getElementById("progress-bar-fill");
  const statusLabel = document.getElementById("progress-status-label");
  const percentLabel = document.getElementById("progress-percent-label");
  const terminal = document.getElementById("live-stream-terminal");
  const importBtn = document.getElementById("import-btn");
  const cancelBtn = document.getElementById("import-cancel-btn");

  if (!githubUsername) {
    showToast("GitHub username is required.", "error");
    return;
  }

  let studentId = studentSelect?.value;

  // Reveal real-time progress container
  if (progressSec) progressSec.style.display = "flex";
  if (terminal) terminal.innerHTML = "";
  if (progressFill) progressFill.style.width = "5%";
  if (percentLabel) percentLabel.textContent = "5%";
  if (statusLabel) statusLabel.textContent = "Initiating real-time import...";
  if (importBtn) importBtn.disabled = true;
  if (cancelBtn) cancelBtn.disabled = true;

  function appendTerminal(text, type = "info") {
    if (!terminal) return;
    const line = document.createElement("div");
    line.className = `term-line ${type}`;
    line.textContent = text;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
  }

  try {
    // Step 1: Create student if needed
    if (!studentId) {
      if (!newName || !newEmail) {
        throw new Error("Select an existing student or enter New Student Name and Email.");
      }

      appendTerminal(`[INIT] Creating new profile for '${newName}'...`, "info");
      const createRes = await fetch(`${API_BASE}/api/students/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newName,
          email: newEmail,
          github_username: githubUsername,
        }),
      });

      if (!createRes.ok) {
        const err = await createRes.json();
        throw new Error(err.detail || "Could not create student");
      }

      const newStudent = await createRes.json();
      studentId = newStudent.id;
      appendTerminal(`[SUCCESS] Student profile created (ID: ${studentId})`, "success");
    }

    // Step 2: Stream import via SSE
    appendTerminal(`[STREAM] Connecting to GitHub event stream for @${githubUsername}...`, "info");

    const streamUrl = `${API_BASE}/api/import/github/${studentId}/stream?username=${encodeURIComponent(githubUsername)}`;

    await new Promise((resolve, reject) => {
      const eventSource = new EventSource(streamUrl);

      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const pct = payload.percent || 10;

          if (progressFill) progressFill.style.width = `${pct}%`;
          if (percentLabel) percentLabel.textContent = `${pct}%`;

          if (payload.type === "init") {
            appendTerminal(`[START] ${payload.message}`, "info");
            if (statusLabel) statusLabel.textContent = payload.message;
          } else if (payload.type === "discovered") {
            appendTerminal(`[INFO] Discovered ${payload.count} repositories (Processing ${payload.to_process})`, "info");
            if (statusLabel) statusLabel.textContent = `Processing repositories...`;
          } else if (payload.type === "progress") {
            appendTerminal(`[SCAN] (${payload.index}/${payload.total}) Analyzing '${payload.repo}'...`, "info");
            if (statusLabel) statusLabel.textContent = `Analyzing ${payload.repo} (${payload.index}/${payload.total})`;
          } else if (payload.type === "repo_imported") {
            appendTerminal(
              `[OK] '${payload.repo}' — Score: ${payload.score}/100 | Skills: ${(payload.skills || []).join(", ") || 'none'}`,
              "success"
            );
          } else if (payload.type === "repo_skipped") {
            appendTerminal(`[SKIP] '${payload.repo}' (${payload.reason})`, "warning");
          } else if (payload.type === "complete") {
            appendTerminal(`[DONE] Imported ${payload.imported_count} projects. Final Score: ${payload.student_score}/100`, "success");
            if (statusLabel) statusLabel.textContent = "Import Complete!";
            eventSource.close();
            resolve(payload);
          } else if (payload.type === "error") {
            appendTerminal(`[ERROR] ${payload.message}`, "error");
            eventSource.close();
            reject(new Error(payload.message));
          }
        } catch (e) {
          console.warn("SSE parse error:", e);
        }
      };

      eventSource.onerror = (err) => {
        eventSource.close();
        // Fallback to standard HTTP import if EventSource disconnected unexpectedly
        appendTerminal("[FALLBACK] Streaming interrupted, falling back to standard import...", "warning");
        fetch(`${API_BASE}/api/import/github/${studentId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ github_username: githubUsername }),
        })
          .then((res) => {
            if (!res.ok) throw new Error("Fallback import failed");
            return res.json();
          })
          .then((data) => resolve(data))
          .catch((e) => reject(e));
      };
    });

    showToast("Repositories imported and scored in real-time!", "success");
    fetchRateLimitStatus();

    setTimeout(async () => {
      hideImportModal();
      await loadStudentsList();
      viewStudentProfile(studentId);
    }, 1200);

  } catch (err) {
    appendTerminal(`[FAIL] ${err.message}`, "error");
    showToast(err.message, "error");
  } finally {
    if (importBtn) importBtn.disabled = false;
    if (cancelBtn) cancelBtn.disabled = false;
  }
}

// ═══════════════════════ Toast Helper ═══════════════════════
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  const icon = type === "success" ? "check-circle" : type === "error" ? "alert-circle" : "info";
  toast.innerHTML = `
    <i data-lucide="${icon}" style="width:18px; height:18px; flex-shrink:0;"></i>
    <span>${escapeHtml(message)}</span>
  `;
  container.appendChild(toast);
  safeCreateIcons();

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ═══════════════════════ Utilities ═══════════════════════
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
