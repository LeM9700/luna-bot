import { useEffect, useState } from 'react'
import { getStats } from '../lib/api'

type Stats = {
  total_users: number
  total_messages: number
  total_memories: number
  premium_users: number
  messages_by_companion: Record<string, number>
  avg_attachment: Record<string, number>
}

const companionMeta: Record<string, { name: string; emoji: string; color: string }> = {
  luna: { name: 'Luna',  emoji: '🌙', color: 'text-violet-400' },
  aria: { name: 'Aria',  emoji: '⚡', color: 'text-yellow-400' },
  sage: { name: 'Sage',  emoji: '🍃', color: 'text-emerald-400' },
}

function StatCard({ label, value, icon, sub }: {
  label: string; value: string | number; icon: string; sub?: string
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
          {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
        </div>
        <span className="text-2xl opacity-70">{icon}</span>
      </div>
    </div>
  )
}

function AttachmentBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full bg-current ${color}`}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="text-sm font-mono w-12 text-right">{value}/100</span>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(() => setError('Impossible de charger les stats. Services démarrés ?'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="p-8 flex items-center justify-center h-full text-gray-500">
      Chargement…
    </div>
  )

  if (error) return (
    <div className="p-8">
      <div className="bg-red-950/50 border border-red-800 rounded-xl p-4 text-red-400">
        {error}
      </div>
    </div>
  )

  if (!stats) return null

  const premiumRate = stats.total_users > 0
    ? Math.round((stats.premium_users / stats.total_users) * 100)
    : 0

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">Dashboard</h1>
      <p className="text-gray-500 text-sm mb-8">Vue d'ensemble en temps réel</p>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Utilisateurs"   value={stats.total_users}    icon="👥" sub={`${stats.premium_users} premium`} />
        <StatCard label="Messages"       value={stats.total_messages} icon="💬" />
        <StatCard label="Souvenirs"      value={stats.total_memories} icon="🧠" />
        <StatCard label="Taux premium"   value={`${premiumRate}%`}    icon="⭐" sub={`${stats.premium_users} abonnés`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Messages par companion */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="font-semibold mb-4 text-gray-300">Messages par companion</h2>
          <div className="space-y-4">
            {Object.entries(stats.messages_by_companion).map(([id, count]) => {
              const meta = companionMeta[id] || { name: id, emoji: '🤖', color: 'text-gray-400' }
              const max = Math.max(...Object.values(stats.messages_by_companion))
              const pct = max > 0 ? Math.round((count / max) * 100) : 0
              return (
                <div key={id}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className={`font-medium ${meta.color}`}>{meta.emoji} {meta.name}</span>
                    <span className="text-gray-400">{count} msgs</span>
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full bg-current ${meta.color}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
            {Object.keys(stats.messages_by_companion).length === 0 && (
              <p className="text-gray-600 text-sm">Aucune conversation enregistrée</p>
            )}
          </div>
        </div>

        {/* Attachement moyen */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="font-semibold mb-4 text-gray-300">Attachement moyen</h2>
          <div className="space-y-4">
            {Object.entries(stats.avg_attachment).map(([id, avg]) => {
              const meta = companionMeta[id] || { name: id, emoji: '🤖', color: 'text-gray-400' }
              return (
                <div key={id}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className={`font-medium ${meta.color}`}>{meta.emoji} {meta.name}</span>
                    <span className="text-gray-400">{avg}/100</span>
                  </div>
                  <AttachmentBar value={avg} color={meta.color} />
                </div>
              )
            })}
            {Object.keys(stats.avg_attachment).length === 0 && (
              <p className="text-gray-600 text-sm">Aucune donnée d'attachement</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
