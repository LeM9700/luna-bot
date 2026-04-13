import { useState, useEffect } from 'react'
import {
  getTrainingCompanions,
  analyzeCompanion,
  getSuggestions,
  applySuggestion,
  resetCompanionPrompt
} from '../lib/api'

type Companion = {
  id: string; name: string; current_prompt: string;
  is_custom: boolean; conversation_count: number
}

type Suggestion = {
  id: number; prompt: string; version: number; is_active: boolean;
  analysis: string; improvements: string[]; created_at: string
}

type AnalysisResult = {
  prompt_id: number; analysis: string; strengths: string[];
  improvements: string[]; new_prompt: string; conversations_analyzed: number
}

const emoji: Record<string, string> = { luna: '🌙', aria: '⚡', sage: '🍃' }

export default function Training() {
  const [companions, setCompanions] = useState<Companion[]>([])
  const [selected, setSelected] = useState<string>('luna')
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [analyzing, setAnalyzing] = useState(false)
  const [lastAnalysis, setLastAnalysis] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [expandedSuggestion, setExpandedSuggestion] = useState<number | null>(null)

  useEffect(() => {
    loadCompanions()
  }, [])

  useEffect(() => {
    if (selected) loadSuggestions(selected)
  }, [selected])

  async function loadCompanions() {
    try {
      const data = await getTrainingCompanions()
      setCompanions(data)
    } catch {
      setError('Impossible de charger les companions. Training service démarré ?')
    }
  }

  async function loadSuggestions(id: string) {
    try {
      const data = await getSuggestions(id)
      setSuggestions(data)
    } catch {
      setSuggestions([])
    }
  }

  async function handleAnalyze() {
    setAnalyzing(true)
    setError('')
    setSuccess('')
    setLastAnalysis(null)
    try {
      const result = await analyzeCompanion(selected)
      setLastAnalysis(result)
      await loadSuggestions(selected)
      setSuccess(`Analyse terminée ! ${result.conversations_analyzed} conversations analysées.`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erreur lors de l\'analyse.'
      setError(msg.includes('400') ? 'Pas assez de conversations (minimum 5).' : msg)
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleApply(promptId: number) {
    try {
      await applySuggestion(selected, promptId)
      setSuccess('Prompt appliqué avec succès !')
      await loadCompanions()
      await loadSuggestions(selected)
    } catch {
      setError('Erreur lors de l\'application du prompt.')
    }
  }

  async function handleReset() {
    try {
      await resetCompanionPrompt(selected)
      setSuccess('Prompt réinitialisé au défaut.')
      await loadCompanions()
      await loadSuggestions(selected)
    } catch {
      setError('Erreur lors de la réinitialisation.')
    }
  }

  const current = companions.find(c => c.id === selected)

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">Entraînement</h1>
      <p className="text-gray-500 text-sm mb-8">
        Analyse les conversations et améliore automatiquement les prompts des companions
      </p>

      {/* Onglets companions */}
      <div className="flex gap-2 mb-6">
        {companions.map(c => (
          <button
            key={c.id}
            onClick={() => { setSelected(c.id); setLastAnalysis(null); setError(''); setSuccess('') }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              selected === c.id
                ? 'bg-luna-700/30 text-luna-400 border border-luna-700/50'
                : 'text-gray-500 hover:text-gray-300 bg-gray-900 border border-gray-800'
            }`}
          >
            <span>{emoji[c.id]}</span>
            {c.name}
            {c.is_custom && <span className="w-1.5 h-1.5 bg-luna-500 rounded-full" title="Prompt personnalisé actif" />}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-950/50 border border-red-800 rounded-xl p-4 text-red-400 text-sm mb-4">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-emerald-950/50 border border-emerald-800 rounded-xl p-4 text-emerald-400 text-sm mb-4">
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Prompt actuel */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-sm text-gray-300">Prompt actuel</h2>
            <div className="flex items-center gap-2">
              {current?.is_custom && (
                <span className="text-xs bg-luna-900/50 text-luna-400 border border-luna-800 px-2 py-0.5 rounded-full">
                  Personnalisé
                </span>
              )}
              {current?.is_custom && (
                <button
                  onClick={handleReset}
                  className="text-xs text-gray-500 hover:text-red-400 transition-colors"
                >
                  Réinitialiser
                </button>
              )}
            </div>
          </div>
          <pre className="text-xs text-gray-400 whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-y-auto">
            {current?.current_prompt || '—'}
          </pre>
        </div>

        {/* Stats & action */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <h2 className="font-semibold text-sm text-gray-300 mb-3">Statistiques</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Conversations analysables</span>
                <span className="font-mono">{current?.conversation_count || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Suggestions générées</span>
                <span className="font-mono">{suggestions.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Prompt actif</span>
                <span className={current?.is_custom ? 'text-luna-400' : 'text-gray-600'}>
                  {current?.is_custom ? 'Personnalisé' : 'Défaut'}
                </span>
              </div>
            </div>
          </div>

          <button
            onClick={handleAnalyze}
            disabled={analyzing || (current?.conversation_count ?? 0) < 5}
            className="mt-6 w-full py-2.5 bg-luna-600 hover:bg-luna-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            {analyzing ? (
              <>
                <span className="animate-spin">⚙️</span>
                Analyse en cours…
              </>
            ) : (
              <>
                🎓 Analyser & générer un nouveau prompt
              </>
            )}
          </button>
          {(current?.conversation_count ?? 0) < 5 && (
            <p className="text-xs text-center text-gray-600 mt-2">
              Minimum 5 conversations requises ({current?.conversation_count || 0}/5)
            </p>
          )}
        </div>
      </div>

      {/* Résultat de la dernière analyse */}
      {lastAnalysis && (
        <div className="bg-gray-900 border border-luna-800/50 rounded-xl p-5 mb-6">
          <h2 className="font-semibold mb-4 text-luna-400">Résultat de l'analyse</h2>
          <p className="text-sm text-gray-300 mb-4">{lastAnalysis.analysis}</p>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <h3 className="text-xs text-emerald-400 font-semibold uppercase mb-2">Points forts</h3>
              <ul className="space-y-1">
                {lastAnalysis.strengths.map((s, i) => (
                  <li key={i} className="text-xs text-gray-400 flex gap-2">
                    <span className="text-emerald-500">✓</span>{s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-xs text-amber-400 font-semibold uppercase mb-2">Améliorations</h3>
              <ul className="space-y-1">
                {lastAnalysis.improvements.map((s, i) => (
                  <li key={i} className="text-xs text-gray-400 flex gap-2">
                    <span className="text-amber-500">→</span>{s}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <button
            onClick={() => handleApply(lastAnalysis.prompt_id)}
            className="px-4 py-2 bg-emerald-700 hover:bg-emerald-600 rounded-lg text-sm font-medium transition-colors"
          >
            ✓ Appliquer ce prompt
          </button>
        </div>
      )}

      {/* Historique des suggestions */}
      {suggestions.length > 0 && (
        <div>
          <h2 className="font-semibold text-sm text-gray-300 mb-3">
            Historique des suggestions ({suggestions.length})
          </h2>
          <div className="space-y-3">
            {suggestions.map(s => (
              <div
                key={s.id}
                className={`bg-gray-900 border rounded-xl p-4 ${
                  s.is_active ? 'border-luna-700/50' : 'border-gray-800'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">Version {s.version}</span>
                    {s.is_active && (
                      <span className="text-xs bg-luna-900/50 text-luna-400 border border-luna-800 px-2 py-0.5 rounded-full">
                        Actif
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-600">
                      {new Date(s.created_at).toLocaleDateString('fr-FR')}
                    </span>
                    <button
                      onClick={() => setExpandedSuggestion(expandedSuggestion === s.id ? null : s.id)}
                      className="text-xs text-gray-500 hover:text-gray-300"
                    >
                      {expandedSuggestion === s.id ? 'Réduire' : 'Voir'}
                    </button>
                    {!s.is_active && (
                      <button
                        onClick={() => handleApply(s.id)}
                        className="text-xs text-luna-500 hover:text-luna-300"
                      >
                        Appliquer
                      </button>
                    )}
                  </div>
                </div>
                {s.analysis && (
                  <p className="text-xs text-gray-500 line-clamp-2">{s.analysis}</p>
                )}
                {expandedSuggestion === s.id && (
                  <pre className="mt-3 text-xs text-gray-400 whitespace-pre-wrap font-mono leading-relaxed bg-gray-950 rounded-lg p-3 max-h-48 overflow-y-auto">
                    {s.prompt}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
