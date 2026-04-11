import { useState, useEffect, useCallback } from "react"
import { api } from "../services/api"
import type { SessionLog, SessionLogCreate } from "../types"

interface UseSessionsReturn {
  sessions:  SessionLog[]
  loading:   boolean
  error:     string | null
  refresh:   () => Promise<void>
  create:    (payload: SessionLogCreate) => Promise<void>
  remove:    (id: number) => Promise<void>
}

export function useSessions(): UseSessionsReturn {
  const [sessions, setSessions] = useState<SessionLog[]>([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await api.sessions.list({ limit: 100 })
      setSessions(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal fetch sessions")
    } finally {
      setLoading(false)
    }
  }, [])

  const create = useCallback(async (payload: SessionLogCreate) => {
    await api.sessions.create(payload)
    await refresh()
  }, [refresh])

  const remove = useCallback(async (id: number) => {
    await api.sessions.delete(id)
    setSessions(prev => prev.filter(s => s.id !== id))
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return { sessions, loading, error, refresh, create, remove }
}
