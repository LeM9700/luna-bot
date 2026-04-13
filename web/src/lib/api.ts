import axios from 'axios'

const chat     = axios.create({ baseURL: '/api/chat' })
const memory   = axios.create({ baseURL: '/api/memory' })
const persona  = axios.create({ baseURL: '/api/persona' })
const training = axios.create({ baseURL: '/api/training' })

// ── Chat ───────────────────────────────────────────────────────────────
export async function sendMessage(payload: {
  user_id: string
  username: string
  companion_id: string
  message: string
  public_key: string
}) {
  const { data } = await chat.post('/chat', payload)
  return data as { reply: string; companion_name: string }
}

// ── Memory ─────────────────────────────────────────────────────────────
export async function getMemories(userId: string) {
  const { data } = await memory.get(`/memories/${userId}`)
  return data.memories as Record<string, string[]>
}

// ── Personality ────────────────────────────────────────────────────────
export async function getCompanionState(userId: string, companionId: string) {
  const { data } = await persona.get(`/state/${userId}/${companionId}`)
  return data as {
    attachment: number
    mood: string
    message_count: number
    last_seen: string | null
    relationship_notes: string | null
  }
}

export async function listCompanions() {
  const { data } = await persona.get('/companions')
  return data.companions as Array<{
    id: string
    name: string
    system: string
    has_custom_prompt: boolean
  }>
}

// ── Training ───────────────────────────────────────────────────────────
export async function getStats() {
  const { data } = await training.get('/stats')
  return data as {
    total_users: number
    total_messages: number
    total_memories: number
    premium_users: number
    messages_by_companion: Record<string, number>
    avg_attachment: Record<string, number>
  }
}

export async function getTrainingCompanions() {
  const { data } = await training.get('/companions')
  return data.companions as Array<{
    id: string
    name: string
    current_prompt: string
    is_custom: boolean
    conversation_count: number
  }>
}

export async function analyzeCompanion(companionId: string) {
  const { data } = await training.post(`/analyze/${companionId}`)
  return data as {
    prompt_id: number
    companion_id: string
    analysis: string
    strengths: string[]
    improvements: string[]
    new_prompt: string
    conversations_analyzed: number
  }
}

export async function getSuggestions(companionId: string) {
  const { data } = await training.get(`/suggestions/${companionId}`)
  return data.suggestions as Array<{
    id: number
    prompt: string
    version: number
    is_active: boolean
    analysis: string
    improvements: string[]
    created_at: string
  }>
}

export async function applySuggestion(companionId: string, promptId: number) {
  const { data } = await training.post(`/apply/${companionId}/${promptId}`)
  return data
}

export async function resetCompanionPrompt(companionId: string) {
  const { data } = await training.post(`/reset/${companionId}`)
  return data
}
