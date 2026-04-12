import { useState, useEffect, useCallback } from "react";

// ── Config ───────────────────────────────────────────────────────────────────
// Production: nginx proxies /api/* → token-api:8000/*
// Development: vite proxies /api/* → localhost:8000/*
const API_URL = import.meta.env.VITE_API_URL || "/api";

const MODELS = {
  claude: [
    { id: "claude-opus-4-6",   label: "Claude Opus 4.6",   inputRate: 15,  outputRate: 75  },
    { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6", inputRate: 3,   outputRate: 15  },
    { id: "claude-haiku-4-5",  label: "Claude Haiku 4.5",  inputRate: 0.8, outputRate: 4   },
  ],
  copilot: [
    { id: "copilot-gpt4o", label: "Copilot (GPT-4o)", inputRate: 5,  outputRate: 15 },
    { id: "copilot-gpt4",  label: "Copilot (GPT-4)",  inputRate: 10, outputRate: 30 },
  ],
};

const ACCOUNTS = {
  claude: [
    { id: "claude-azmi",  label: "Claude Pro · azmi.codes"  },
    { id: "claude-figul", label: "Claude Pro · figulazmi"   },
  ],
  copilot: [
    { id: "copilot-azmi", label: "Copilot · azmi.codes" },
  ],
};

const ACCOUNT_META = {
  "claude-azmi":  { label: "Claude · azmi.codes",  color: "#FF6B35" },
  "claude-figul": { label: "Claude · figulazmi",   color: "#9B59B6" },
  "copilot-azmi": { label: "Copilot · azmi.codes", color: "#0078D4" },
};

// ── Helpers ──────────────────────────────────────────────────────────────────
function calcCost(log) {
  const allModels = [...MODELS.claude, ...MODELS.copilot];
  const model = allModels.find((m) => m.id === log.model);
  if (!model) return 0;
  return (log.inputTokens / 1_000_000) * model.inputRate +
         (log.outputTokens / 1_000_000) * model.outputRate;
}

function fmtTokens(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

function fmtCost(n) { return "$" + n.toFixed(4); }

function timeAgo(ts) {
  const diff = Date.now() - new Date(ts).getTime();
  const h = Math.floor(diff / 3_600_000);
  const d = Math.floor(h / 24);
  if (d > 0) return `${d}d ago`;
  if (h > 0) return `${h}h ago`;
  return "just now";
}

// ── Styles ───────────────────────────────────────────────────────────────────
const S = {
  select: {
    background: "#0A0A0F", border: "1px solid #1E1E2E", borderRadius: 6,
    color: "#ccc", padding: "8px 10px", fontSize: 11, width: "100%",
    fontFamily: "inherit",
  },
  input: {
    background: "#0A0A0F", border: "1px solid #1E1E2E", borderRadius: 6,
    color: "#ccc", padding: "8px 10px", fontSize: 11,
    fontFamily: "inherit", width: "100%", boxSizing: "border-box",
  },
};

// ── Component ─────────────────────────────────────────────────────────────────
export default function TokenMonitor() {
  const [sessions, setSessions]   = useState([]);
  const [stats, setStats]         = useState(null);
  const [loading, setLoading]     = useState(true);
  const [apiError, setApiError]   = useState(false);
  const [showForm, setShowForm]   = useState(false);
  const [filter, setFilter]       = useState("all");
  const [activeTab, setActiveTab] = useState("dashboard");
  const [form, setForm] = useState({
    platform: "claude",
    account:  "claude-azmi",
    model:    "claude-sonnet-4-6",
    inputTokens: "", outputTokens: "", label: "", project: "",
  });

  // ── Fetch dari API ──────────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    try {
      const [sessRes, statRes] = await Promise.all([
        fetch(`${API_URL}/sessions?limit=100`),
        fetch(`${API_URL}/stats`),
      ]);
      if (!sessRes.ok || !statRes.ok) throw new Error("API error");

      const sessData = await sessRes.json();
      const statData = await statRes.json();

      setSessions(sessData.map(s => ({
        id:           s.id,
        platform:     s.platform,
        account:      s.account || null,
        model:        s.model,
        inputTokens:  s.input_tokens,
        outputTokens: s.output_tokens,
        label:        s.label || "Untitled session",
        project:      s.project || "",
        gitBranch:    s.git_branch || "",
        ts:           s.logged_at,
      })));
      setStats(statData);
      setApiError(false);
    } catch {
      setApiError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // ── Platform change → reset account + model ─────────────────────────────
  function handlePlatformChange(p) {
    setForm(f => ({
      ...f,
      platform: p,
      account:  ACCOUNTS[p][0].id,
      model:    MODELS[p][0].id,
    }));
  }

  // ── Log session baru via API ────────────────────────────────────────────
  async function handleAdd() {
    if (!form.inputTokens || !form.outputTokens || !form.label) return;
    try {
      const res = await fetch(`${API_URL}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          platform:      form.platform,
          account:       form.account,
          model:         form.model,
          input_tokens:  parseInt(form.inputTokens),
          output_tokens: parseInt(form.outputTokens),
          label:         form.label,
          project:       form.project || undefined,
        }),
      });
      if (!res.ok) throw new Error("API error");
      setForm({ platform: "claude", account: "claude-azmi", model: "claude-sonnet-4-6", inputTokens: "", outputTokens: "", label: "", project: "" });
      setShowForm(false);
      fetchData();
    } catch {
      alert("Gagal menyimpan ke API. Pastikan backend berjalan.");
    }
  }

  // ── Delete session ──────────────────────────────────────────────────────
  async function handleDelete(id) {
    try {
      await fetch(`${API_URL}/sessions/${id}`, { method: "DELETE" });
      setSessions(prev => prev.filter(s => s.id !== id));
    } catch { /* silent */ }
  }

  // ── Derived data ────────────────────────────────────────────────────────
  const filtered    = filter === "all" ? sessions : sessions.filter(l => l.platform === filter);
  const totalInput  = filtered.reduce((s, l) => s + l.inputTokens, 0);
  const totalOutput = filtered.reduce((s, l) => s + l.outputTokens, 0);
  const totalCost   = filtered.reduce((s, l) => s + calcCost(l), 0);
  const totalTokens = totalInput + totalOutput;

  const hourBuckets = Array(24).fill(0);
  sessions.forEach(l => { hourBuckets[new Date(l.ts).getHours()] += l.inputTokens + l.outputTokens; });
  const maxBucket = Math.max(...hourBuckets, 1);
  const peakHour  = hourBuckets.indexOf(Math.max(...hourBuckets));

  const topSessions = [...sessions]
    .sort((a, b) => (b.inputTokens + b.outputTokens) - (a.inputTokens + a.outputTokens))
    .slice(0, 3);
  const barMax = Math.max(...sessions.map(l => l.inputTokens + l.outputTokens), 1);

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: "100vh", background: "#0A0A0F", color: "#E8E8F0", fontFamily: "'DM Mono','Fira Code',monospace" }}>

      {/* Header */}
      <div style={{ borderBottom: "1px solid #1E1E2E", padding: "20px 28px 0", background: "#0D0D14" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: 8, background: "linear-gradient(135deg,#FF6B35,#0078D4)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>⬡</div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: "0.05em", color: "#fff" }}>TOKEN MONITOR</div>
              <div style={{ fontSize: 10, color: apiError ? "#cc4444" : "#555", letterSpacing: "0.1em" }}>
                {apiError ? "⚠ API OFFLINE" : "CLAUDE CODE · COPILOT · 3 ACCOUNTS"}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={fetchData} style={{ background: "#1E1E2E", border: "none", borderRadius: 6, color: "#888", padding: "8px 12px", fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>↻ REFRESH</button>
            <button onClick={() => setShowForm(!showForm)} style={{ background: showForm ? "#1E1E2E" : "linear-gradient(135deg,#FF6B35,#c94b1a)", border: "none", borderRadius: 6, color: "#fff", padding: "8px 16px", fontSize: 11, cursor: "pointer", letterSpacing: "0.08em", fontFamily: "inherit" }}>
              {showForm ? "✕ CANCEL" : "+ LOG SESSION"}
            </button>
          </div>
        </div>
        <div style={{ display: "flex", gap: 0 }}>
          {["dashboard", "sessions"].map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{ background: "none", border: "none", cursor: "pointer", padding: "8px 20px", fontSize: 11, letterSpacing: "0.1em", color: activeTab === tab ? "#FF6B35" : "#444", borderBottom: activeTab === tab ? "2px solid #FF6B35" : "2px solid transparent", fontFamily: "inherit", textTransform: "uppercase" }}>{tab}</button>
          ))}
        </div>
      </div>

      <div style={{ padding: "24px 28px", maxWidth: 960, margin: "0 auto" }}>

        {/* Loading / Error */}
        {loading && <div style={{ textAlign: "center", color: "#555", padding: 40, fontSize: 12 }}>Connecting to API...</div>}
        {apiError && !loading && (
          <div style={{ background: "#1A0A0A", border: "1px solid #3A1A1A", borderRadius: 10, padding: 16, marginBottom: 20, fontSize: 11, color: "#cc6666" }}>
            ⚠ Cannot connect to API at <code>{API_URL}</code>. Make sure the backend is running.
            <button onClick={fetchData} style={{ marginLeft: 12, background: "none", border: "1px solid #cc6666", borderRadius: 4, color: "#cc6666", padding: "4px 10px", cursor: "pointer", fontSize: 10, fontFamily: "inherit" }}>RETRY</button>
          </div>
        )}

        {/* Add Form */}
        {showForm && (
          <div style={{ background: "#0D0D14", border: "1px solid #1E1E2E", borderRadius: 10, padding: 20, marginBottom: 24 }}>
            <div style={{ fontSize: 11, letterSpacing: "0.1em", color: "#FF6B35", marginBottom: 16 }}>NEW SESSION LOG</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>PLATFORM</div>
                <select value={form.platform} onChange={e => handlePlatformChange(e.target.value)} style={S.select}>
                  <option value="claude">Claude Code CLI</option>
                  <option value="copilot">GitHub Copilot</option>
                </select>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>ACCOUNT</div>
                <select value={form.account} onChange={e => setForm(f => ({ ...f, account: e.target.value }))} style={S.select}>
                  {ACCOUNTS[form.platform].map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>MODEL</div>
                <select value={form.model} onChange={e => setForm(f => ({ ...f, model: e.target.value }))} style={S.select}>
                  {MODELS[form.platform].map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>INPUT TOKENS</div>
                <input type="number" placeholder="12000" value={form.inputTokens} onChange={e => setForm(f => ({ ...f, inputTokens: e.target.value }))} style={S.input} />
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>OUTPUT TOKENS</div>
                <input type="number" placeholder="3000" value={form.outputTokens} onChange={e => setForm(f => ({ ...f, outputTokens: e.target.value }))} style={S.input} />
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>PROJECT</div>
                <input type="text" placeholder="petrochina-eproc" value={form.project} onChange={e => setForm(f => ({ ...f, project: e.target.value }))} style={S.input} />
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>SESSION LABEL</div>
                <input type="text" placeholder="e.g. SDL middleware refactor" value={form.label} onChange={e => setForm(f => ({ ...f, label: e.target.value }))} style={S.input} />
              </div>
            </div>
            {form.inputTokens && form.outputTokens && (
              <div style={{ marginTop: 12, fontSize: 11, color: "#888" }}>
                Est. cost: <span style={{ color: "#FF6B35" }}>{fmtCost(calcCost({ model: form.model, inputTokens: +form.inputTokens, outputTokens: +form.outputTokens }))}</span>
              </div>
            )}
            <button onClick={handleAdd} style={{ marginTop: 16, background: "linear-gradient(135deg,#FF6B35,#c94b1a)", border: "none", borderRadius: 6, color: "#fff", padding: "10px 24px", fontSize: 11, cursor: "pointer", letterSpacing: "0.08em", fontFamily: "inherit" }}>SAVE TO API</button>
          </div>
        )}

        {!loading && activeTab === "dashboard" && (
          <>
            {/* Stats Row */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 20 }}>
              {[
                { label: "TOTAL TOKENS", value: fmtTokens(totalTokens), sub: `${fmtTokens(totalInput)} in · ${fmtTokens(totalOutput)} out` },
                { label: "EST. COST",    value: fmtCost(totalCost),     sub: "at API rates" },
                { label: "SESSIONS",     value: sessions.length,         sub: "from database" },
              ].map((s, i) => (
                <div key={i} style={{ background: "#0D0D14", border: "1px solid #1E1E2E", borderRadius: 10, padding: "16px 18px" }}>
                  <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.12em", marginBottom: 6 }}>{s.label}</div>
                  <div style={{ fontSize: 26, fontWeight: 700, color: "#fff", letterSpacing: "-0.02em" }}>{s.value}</div>
                  <div style={{ fontSize: 10, color: "#555", marginTop: 2 }}>{s.sub}</div>
                </div>
              ))}
            </div>

            {/* By Account — 3 accounts */}
            <div style={{ background: "#0D0D14", border: "1px solid #1E1E2E", borderRadius: 10, padding: "16px 18px", marginBottom: 20 }}>
              <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.12em", marginBottom: 14 }}>BY ACCOUNT</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
                {(stats?.by_account || []).map(a => {
                  const meta  = ACCOUNT_META[a.account] || { label: a.account, color: "#888" };
                  const total = stats?.total_cost_usd || 0;
                  const pct   = total > 0 ? Math.round(a.cost_usd / total * 100) : 0;
                  return (
                    <div key={a.account} style={{ borderLeft: `3px solid ${meta.color}`, paddingLeft: 12 }}>
                      <div style={{ fontSize: 10, color: "#666", marginBottom: 4 }}>{meta.label}</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: meta.color }}>{fmtCost(a.cost_usd)}</div>
                      <div style={{ fontSize: 10, color: "#444", marginTop: 2 }}>{a.sessions} sessions · {pct}%</div>
                    </div>
                  );
                })}
                {(!stats?.by_account || stats.by_account.length === 0) && (
                  <div style={{ gridColumn: "1/-1", fontSize: 11, color: "#333", textAlign: "center", padding: 8 }}>No data yet</div>
                )}
              </div>
            </div>

            {/* Platform Breakdown */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
              {[
                { key: "claude",  label: "Claude Code CLI", color: "#FF6B35" },
                { key: "copilot", label: "GitHub Copilot",  color: "#0078D4" },
              ].map(p => {
                const stat = stats?.by_platform?.find(r => r.platform === p.key);
                const cost = stat?.cost_usd || 0;
                const total = stats?.total_cost_usd || 0;
                const pct   = total > 0 ? Math.round(cost / total * 100) : 0;
                return (
                  <div key={p.key} style={{ background: "#0D0D14", border: `1px solid ${p.color}22`, borderRadius: 10, padding: "16px 18px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", background: p.color }} />
                        <span style={{ fontSize: 11, color: "#888" }}>{p.label}</span>
                      </div>
                      <span style={{ fontSize: 10, color: p.color }}>{pct}%</span>
                    </div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: p.color }}>{fmtCost(cost)}</div>
                    <div style={{ fontSize: 10, color: "#444", marginTop: 2 }}>{stat?.sessions || 0} sessions</div>
                    <div style={{ marginTop: 12, height: 4, background: "#1E1E2E", borderRadius: 2, overflow: "hidden" }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: p.color, borderRadius: 2 }} />
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Activity by Hour */}
            <div style={{ background: "#0D0D14", border: "1px solid #1E1E2E", borderRadius: 10, padding: "16px 18px", marginBottom: 20 }}>
              <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.12em", marginBottom: 14 }}>ACTIVITY BY HOUR</div>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 48 }}>
                {hourBuckets.map((val, h) => (
                  <div key={h} style={{ flex: 1 }}>
                    <div style={{ width: "100%", height: `${Math.max(4, (val / maxBucket) * 44)}px`, background: h === peakHour ? "#FF6B35" : "#1E1E2E", borderRadius: 2 }} />
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 9, color: "#333" }}>
                <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:00</span>
              </div>
              {sessions.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 10, color: "#666" }}>
                  Peak: <span style={{ color: "#FF6B35" }}>{String(peakHour).padStart(2, "0")}:00</span>
                  {" · "}{fmtTokens(hourBuckets[peakHour])} tokens
                </div>
              )}
            </div>

            {/* Top Sessions */}
            <div style={{ background: "#0D0D14", border: "1px solid #1E1E2E", borderRadius: 10, padding: "16px 18px" }}>
              <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.12em", marginBottom: 14 }}>HEAVIEST SESSIONS</div>
              {topSessions.map((l, i) => {
                const total = l.inputTokens + l.outputTokens;
                const pct   = Math.round(total / barMax * 100);
                const meta  = ACCOUNT_META[l.account] || { color: "#888" };
                return (
                  <div key={l.id} style={{ marginBottom: 14 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 10, color: "#333" }}>#{i + 1}</span>
                        <div style={{ width: 6, height: 6, borderRadius: "50%", background: meta.color }} />
                        <span style={{ fontSize: 11, color: "#ccc" }}>{l.label}</span>
                        {l.project && <span style={{ fontSize: 9, color: "#333", background: "#1A1A24", padding: "2px 6px", borderRadius: 4 }}>{l.project}</span>}
                      </div>
                      <span style={{ fontSize: 11, color: meta.color }}>{fmtTokens(total)}</span>
                    </div>
                    <div style={{ height: 3, background: "#1A1A24", borderRadius: 2, overflow: "hidden" }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: meta.color, borderRadius: 2 }} />
                    </div>
                  </div>
                );
              })}
              {sessions.length === 0 && <div style={{ fontSize: 11, color: "#333", textAlign: "center", padding: 20 }}>No sessions yet. Start coding!</div>}
            </div>
          </>
        )}

        {!loading && activeTab === "sessions" && (
          <>
            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
              {["all", "claude", "copilot"].map(f => (
                <button key={f} onClick={() => setFilter(f)} style={{ background: filter === f ? "#1E1E2E" : "none", border: `1px solid ${filter === f ? "#FF6B35" : "#1E1E2E"}`, borderRadius: 6, color: filter === f ? "#FF6B35" : "#444", padding: "6px 14px", fontSize: 10, cursor: "pointer", letterSpacing: "0.08em", fontFamily: "inherit", textTransform: "uppercase" }}>{f}</button>
              ))}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[...filtered].map(l => {
                const total = l.inputTokens + l.outputTokens;
                const cost  = calcCost(l);
                const meta  = ACCOUNT_META[l.account] || { color: "#888", label: l.platform };
                return (
                  <div key={l.id} style={{ background: "#0D0D14", border: "1px solid #1E1E2E", borderRadius: 10, padding: "14px 16px", display: "flex", alignItems: "center", gap: 14 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: meta.color, flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, color: "#ddd", marginBottom: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{l.label}</div>
                      <div style={{ fontSize: 10, color: "#444" }}>
                        {meta.label}
                        {l.project && ` · ${l.project}`}
                        {l.gitBranch && ` · ${l.gitBranch}`}
                        {" · "}{timeAgo(l.ts)}
                      </div>
                    </div>
                    <div style={{ textAlign: "right", flexShrink: 0 }}>
                      <div style={{ fontSize: 13, color: "#fff", fontWeight: 600 }}>{fmtTokens(total)}</div>
                      <div style={{ fontSize: 10, color: meta.color }}>{fmtCost(cost)}</div>
                    </div>
                    <button onClick={() => handleDelete(l.id)} style={{ background: "none", border: "none", color: "#2A2A3A", cursor: "pointer", fontSize: 14, padding: 4, flexShrink: 0 }} title="Delete">✕</button>
                  </div>
                );
              })}
              {filtered.length === 0 && <div style={{ fontSize: 11, color: "#333", textAlign: "center", padding: 40 }}>No sessions.</div>}
            </div>
          </>
        )}

        <div style={{ marginTop: 24, fontSize: 10, color: "#2A2A3A", textAlign: "center" }}>
          {apiError ? `Offline · ${API_URL}` : `Connected · ${API_URL}`}
        </div>
      </div>
    </div>
  );
}
