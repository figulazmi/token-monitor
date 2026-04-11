import { useState } from "react"
import { useSessions, useStats } from "./hooks"
import { StatsCard, SessionList } from "./components"
import type { SessionLogCreate, Platform } from "./types"

const MODELS = {
  claude:  ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
  copilot: ["copilot-gpt4o", "copilot-gpt4"],
}

function fmtTokens(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M"
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + "K"
  return String(n)
}

function fmtCost(n: number) { return "$" + n.toFixed(4) }

export default function App() {
  const { sessions, loading: sessLoading, error, refresh, create, remove } = useSessions()
  const { stats } = useStats()

  const [tab, setTab]           = useState<"dashboard" | "sessions">("dashboard")
  const [filter, setFilter]     = useState<"all" | Platform>("all")
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<{
    platform: Platform; model: string
    inputTokens: string; outputTokens: string
    label: string; project: string
  }>({ platform: "claude", model: "claude-sonnet-4-6", inputTokens: "", outputTokens: "", label: "", project: "" })

  const apiUrl = import.meta.env.VITE_API_URL ?? "http://192.168.18.169:8000"

  async function handleCreate() {
    if (!form.inputTokens || !form.outputTokens || !form.label) return
    const payload: SessionLogCreate = {
      platform:      form.platform,
      model:         form.model,
      input_tokens:  parseInt(form.inputTokens),
      output_tokens: parseInt(form.outputTokens),
      label:         form.label,
      project:       form.project || undefined,
    }
    await create(payload)
    setForm({ platform: "claude", model: "claude-sonnet-4-6", inputTokens: "", outputTokens: "", label: "", project: "" })
    setShowForm(false)
  }

  const filtered = filter === "all" ? sessions : sessions.filter(s => s.platform === filter)

  const S = {
    input: { background: "#0A0A0F", border: "1px solid #1E1E2E", borderRadius: 6, color: "#ccc", padding: "8px 10px", fontSize: 11, fontFamily: "inherit", width: "100%", boxSizing: "border-box" as const },
    select: { background: "#0A0A0F", border: "1px solid #1E1E2E", borderRadius: 6, color: "#ccc", padding: "8px 10px", fontSize: 11, fontFamily: "inherit", width: "100%" },
  }

  return (
    <div style={{ minHeight: "100vh", background: "#0A0A0F", color: "#E8E8F0", fontFamily: "'DM Mono','Fira Code',monospace" }}>

      {/* Header */}
      <div style={{ borderBottom: "1px solid #1E1E2E", padding: "20px 28px 0", background: "#0D0D14" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: 8, background: "linear-gradient(135deg,#FF6B35,#0078D4)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>⬡</div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: "0.05em", color: "#fff" }}>TOKEN MONITOR</div>
              <div style={{ fontSize: 10, color: error ? "#cc4444" : "#555", letterSpacing: "0.1em" }}>
                {error ? `⚠ API OFFLINE · ${apiUrl}` : `CLAUDE CODE · COPILOT · ${apiUrl}`}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={refresh} style={{ background: "#1E1E2E", border: "none", borderRadius: 6, color: "#888", padding: "8px 12px", fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>↻</button>
            <button onClick={() => setShowForm(v => !v)} style={{ background: showForm ? "#1E1E2E" : "linear-gradient(135deg,#FF6B35,#c94b1a)", border: "none", borderRadius: 6, color: "#fff", padding: "8px 16px", fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>
              {showForm ? "✕ CANCEL" : "+ LOG SESSION"}
            </button>
          </div>
        </div>
        <div style={{ display: "flex" }}>
          {(["dashboard", "sessions"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} style={{ background: "none", border: "none", cursor: "pointer", padding: "8px 20px", fontSize: 11, letterSpacing: "0.1em", color: tab === t ? "#FF6B35" : "#444", borderBottom: tab === t ? "2px solid #FF6B35" : "2px solid transparent", fontFamily: "inherit", textTransform: "uppercase" }}>{t}</button>
          ))}
        </div>
      </div>

      <div style={{ padding: "24px 28px", maxWidth: 900, margin: "0 auto" }}>

        {/* Error */}
        {error && (
          <div style={{ background: "#1A0A0A", border: "1px solid #3A1A1A", borderRadius: 10, padding: 14, marginBottom: 20, fontSize: 11, color: "#cc6666" }}>
            ⚠ {error}
            <button onClick={refresh} style={{ marginLeft: 12, background: "none", border: "1px solid #cc6666", borderRadius: 4, color: "#cc6666", padding: "4px 10px", cursor: "pointer", fontSize: 10, fontFamily: "inherit" }}>RETRY</button>
          </div>
        )}

        {/* Log Form */}
        {showForm && (
          <div style={{ background: "#0D0D14", border: "1px solid #1E1E2E", borderRadius: 10, padding: 20, marginBottom: 24 }}>
            <div style={{ fontSize: 11, letterSpacing: "0.1em", color: "#FF6B35", marginBottom: 16 }}>NEW SESSION LOG</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>PLATFORM</div>
                <select value={form.platform} style={S.select}
                  onChange={e => { const p = e.target.value as Platform; setForm(f => ({ ...f, platform: p, model: MODELS[p][0] })) }}>
                  <option value="claude">Claude Code CLI</option>
                  <option value="copilot">GitHub Copilot</option>
                </select>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>MODEL</div>
                <select value={form.model} style={S.select} onChange={e => setForm(f => ({ ...f, model: e.target.value }))}>
                  {MODELS[form.platform].map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>INPUT TOKENS</div>
                <input type="number" placeholder="12000" value={form.inputTokens} style={S.input} onChange={e => setForm(f => ({ ...f, inputTokens: e.target.value }))} />
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>OUTPUT TOKENS</div>
                <input type="number" placeholder="3000" value={form.outputTokens} style={S.input} onChange={e => setForm(f => ({ ...f, outputTokens: e.target.value }))} />
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>LABEL</div>
                <input type="text" placeholder="SDL middleware refactor" value={form.label} style={S.input} onChange={e => setForm(f => ({ ...f, label: e.target.value }))} />
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>PROJECT</div>
                <input type="text" placeholder="petrochina-eproc" value={form.project} style={S.input} onChange={e => setForm(f => ({ ...f, project: e.target.value }))} />
              </div>
            </div>
            <button onClick={handleCreate} style={{ marginTop: 16, background: "linear-gradient(135deg,#FF6B35,#c94b1a)", border: "none", borderRadius: 6, color: "#fff", padding: "10px 24px", fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>
              SAVE TO API
            </button>
          </div>
        )}

        {sessLoading && <div style={{ textAlign: "center", color: "#444", padding: 40, fontSize: 12 }}>Loading...</div>}

        {!sessLoading && tab === "dashboard" && stats && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 24 }}>
              <StatsCard label="TOTAL TOKENS"  value={fmtTokens(stats.total_input_tokens + stats.total_output_tokens)} sub={`${fmtTokens(stats.total_input_tokens)} in · ${fmtTokens(stats.total_output_tokens)} out`} />
              <StatsCard label="EST. COST"     value={fmtCost(stats.total_cost_usd)} sub="at API rates" />
              <StatsCard label="SESSIONS"      value={stats.total_sessions} sub="from database" />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 24 }}>
              {stats.by_platform.map(p => {
                const color = p.platform === "claude" ? "#FF6B35" : "#0078D4"
                const pct   = stats.total_cost_usd > 0 ? Math.round(p.cost_usd / stats.total_cost_usd * 100) : 0
                return (
                  <div key={p.platform} style={{ background: "#0D0D14", border: `1px solid ${color}22`, borderRadius: 10, padding: "16px 18px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />
                        <span style={{ fontSize: 11, color: "#888" }}>{p.platform === "claude" ? "Claude Code CLI" : "GitHub Copilot"}</span>
                      </div>
                      <span style={{ fontSize: 10, color }}>{pct}%</span>
                    </div>
                    <div style={{ fontSize: 22, fontWeight: 700, color }}>{fmtCost(p.cost_usd)}</div>
                    <div style={{ fontSize: 10, color: "#444", marginTop: 2 }}>{p.sessions} sessions</div>
                    <div style={{ marginTop: 12, height: 4, background: "#1E1E2E", borderRadius: 2 }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2 }} />
                    </div>
                  </div>
                )
              })}
            </div>

            {stats.peak_hour !== null && (
              <div style={{ background: "#0D0D14", border: "1px solid #1E1E2E", borderRadius: 10, padding: "16px 18px" }}>
                <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.12em", marginBottom: 8 }}>PEAK HOUR</div>
                <div style={{ fontSize: 14, color: "#FF6B35" }}>
                  {String(stats.peak_hour).padStart(2, "0")}:00 – {String(stats.peak_hour + 1).padStart(2, "0")}:00
                </div>
              </div>
            )}
          </>
        )}

        {!sessLoading && tab === "sessions" && (
          <>
            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
              {(["all", "claude", "copilot"] as const).map(f => (
                <button key={f} onClick={() => setFilter(f)} style={{ background: filter === f ? "#1E1E2E" : "none", border: `1px solid ${filter === f ? "#FF6B35" : "#1E1E2E"}`, borderRadius: 6, color: filter === f ? "#FF6B35" : "#444", padding: "6px 14px", fontSize: 10, cursor: "pointer", fontFamily: "inherit", textTransform: "uppercase" }}>{f}</button>
              ))}
            </div>
            <SessionList sessions={filtered} onDelete={remove} />
          </>
        )}

        <div style={{ marginTop: 24, fontSize: 10, color: "#2A2A3A", textAlign: "center" }}>
          {error ? `Offline · ${apiUrl}` : `Connected · ${apiUrl}`}
        </div>
      </div>
    </div>
  )
}
