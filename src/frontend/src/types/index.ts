export type Platform = "claude" | "copilot"

export interface SessionLog {
  id:           number
  platform:     Platform
  model:        string
  input_tokens: number
  output_tokens: number
  cost_usd:     number
  label:        string | null
  git_branch:   string | null
  project:      string | null
  logged_at:    string
}

export interface SessionLogCreate {
  platform:      Platform
  model:         string
  input_tokens:  number
  output_tokens: number
  label?:        string
  git_branch?:   string
  project?:      string
}

export interface PlatformStat {
  platform: Platform
  cost_usd: number
  sessions: number
}

export interface ModelStat {
  model:    string
  tokens:   number
  cost_usd: number
}

export interface Stats {
  total_input_tokens:  number
  total_output_tokens: number
  total_cost_usd:      number
  total_sessions:      number
  by_platform:         PlatformStat[]
  by_model:            ModelStat[]
  peak_hour:           number | null
}
