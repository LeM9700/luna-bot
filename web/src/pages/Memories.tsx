import { useState } from 'react'
import { getMemories } from '../lib/api'

const categoryMeta: Record<string, { label: string; emoji: string; color: string }> = {
  preference:   { label: 'Préférences',   emoji: '❤️',  color: 'text-rose-400 border-rose-800 bg-rose-950/20' },
  emotion:      { label: 'Émotions',      emoji: '💭',  color: 'text-purple-400 border-purple-800 bg-purple-950/20' },
  fact:         { label: 'Faits perso',   emoji: '📌',  color: 'text-blue-400 border-blue-800 bg-blue-950/20' },
  goal:         { label: 'Objectifs',     emoji: '🎯',  color: 'text-orange-400 border-orange-800 bg-orange-950/20' },
  relationship: { label: 'Proches',       emoji: '👥',  color: 'text-teal-400 border-teal-800 bg-teal-950/20' },
  general:      { label: 'Autres',        emoji: '📝',  color: 'text-gray-400 border-gray-700 bg-gray-800/30' },
}

export default function Memories() {
  const [userId, setUserId] = useState('')
  const [memories, setMemories] = useState<Record<string, string[]> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSearch() {
    if (!userId.trim()) return
    setLoading(true)
    setError('')
    setMemories(null)
    try {
      const data = await getMemories(userId.trim())
      setMemories(data)
    } catch {
      setError('Impossible de récupérer les souvenirs. Vérifiez l\'ID utilisateur.')
    } finally {
      setLoading(false)
    }
  }

  const totalMemories = memories
    ? Object.values(memories).reduce((sum, arr) => sum + arr.length, 0)
    : 0

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">Mémoires</h1>
      <p className="text-gray-500 text-sm mb-8">Consultez les souvenirs d'un utilisateur</p>

      {/* Recherche */}
      <div className="flex gap-3 mb-8">
        <input
          type="text"
          value={userId}
          onChange={e => setUserId(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="ID utilisateur Telegram (ex: 123456789)"
          className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-luna-600 placeholder-gray-600"
        />
        <button
          onClick={handleSearch}
          disabled={!userId.trim() || loading}
          className="px-5 py-2.5 bg-luna-600 hover:bg-luna-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-sm font-medium transition-colors"
        >
          {loading ? 'Recherche…' : 'Rechercher'}
        </button>
      </div>

      {error && (
        <div className="bg-red-950/50 border border-red-800 rounded-xl p-4 text-red-400 text-sm mb-6">
          {error}
        </div>
      )}

      {memories !== null && (
        <>
          {totalMemories === 0 ? (
            <div className="text-center py-16 text-gray-600">
              <p className="text-4xl mb-4">🧠</p>
              <p>Aucun souvenir pour cet utilisateur</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-5">
                <p className="text-sm text-gray-400">
                  <span className="font-semibold text-white">{totalMemories}</span> souvenir(s) pour l'utilisateur <span className="font-mono text-luna-400">{userId}</span>
                </p>
                <span className="text-xs text-gray-600">{Object.keys(memories).length} catégorie(s)</span>
              </div>
              <div className="grid gap-4">
                {Object.entries(memories).map(([cat, items]) => {
                  const meta = categoryMeta[cat] || { label: cat, emoji: '📝', color: 'text-gray-400 border-gray-700 bg-gray-800/30' }
                  return (
                    <div key={cat} className={`border rounded-xl p-5 ${meta.color}`}>
                      <h2 className="font-semibold mb-3 flex items-center gap-2">
                        <span>{meta.emoji}</span>
                        {meta.label}
                        <span className="ml-auto text-xs opacity-60">{items.length}</span>
                      </h2>
                      <ul className="space-y-1.5">
                        {items.map((item, i) => (
                          <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                            <span className="opacity-40 mt-0.5">•</span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
