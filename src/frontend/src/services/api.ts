import type { SessionLog, SessionLogCreate, Stats } from "../types"

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://192.168.18.169:8010"

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${path}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () =>
    request<{ status: string; timestamp: string }>("/health"),

  sessions: {
    list: (params?: { platform?: string; project?: string; limit?: number }) => {
      const qs = new URLSearchParams()
      if (params?.platform) qs.set("platform", params.platform)
      if (params?.project)  qs.set("project", params.project)
      if (params?.limit)    qs.set("limit", String(params.limit))
      return request<SessionLog[]>(`/sessions?${qs.toString()}`)
    },

    create: (payload: SessionLogCreate) =>
      request<SessionLog>("/sessions", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    delete: (id: number) =>
      request<{ deleted: number }>(`/sessions/${id}`, { method: "DELETE" }),
  },

  stats: {
    get: () => request<Stats>("/stats"),
  },
}
