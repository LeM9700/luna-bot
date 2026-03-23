import { useState, useRef, useEffect } from 'react'
import { sendMessage } from '../lib/api'

type Message = { role: 'user' | 'assistant'; content: string; name?: string }

const companions = [
  { id: 'luna', name: 'Luna',  emoji: '🌙', desc: 'Douce & empathique' },
  { id: 'aria', name: 'Aria',  emoji: '⚡', desc: 'Directe & piquante' },
  { id: 'sage', name: 'Sage',  emoji: '🍃', desc: 'Philosophique' },
]

export default function Chat() {
  const [companionId, setCompanionId] = useState('luna')
  const [userId] = useState(() => `web_${Math.random().toString(36).slice(2, 9)}`)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const companion = companions.find(c => c.id === companionId)!

  async function handleSend() {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    try {
      const resp = await sendMessage({
        user_id:      userId,
        username:     'web_user',
        companion_id: companionId,
        message:      userMsg,
        public_key:   'web_no_encryption'
      })
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: resp.reply,
        name: resp.companion_name
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Erreur de connexion au chat-service.'
      }])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-900 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{companion.emoji}</span>
          <div>
            <h1 className="font-semibold">{companion.name}</h1>
            <p className="text-xs text-gray-500">{companion.desc}</p>
          </div>
        </div>

        {/* Sélecteur de companion */}
        <div className="flex gap-2">
          {companions.map(c => (
            <button
              key={c.id}
              onClick={() => { setCompanionId(c.id); setMessages([]) }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                companionId === c.id
                  ? 'bg-luna-700/40 text-luna-400 border border-luna-700/50'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800'
              }`}
            >
              {c.emoji} {c.name}
            </button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-600 mt-16">
            <p className="text-4xl mb-4">{companion.emoji}</p>
            <p className="font-medium text-gray-400">Commencer une conversation avec {companion.name}</p>
            <p className="text-sm mt-1">{companion.desc}</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-lg rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-luna-700/40 text-white rounded-br-sm'
                  : 'bg-gray-800 text-gray-100 rounded-bl-sm'
              }`}
            >
              {msg.role === 'assistant' && msg.name && (
                <p className="text-xs text-luna-400 font-medium mb-1">{companion.emoji} {msg.name}</p>
              )}
              {msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 rounded-2xl rounded-bl-sm px-4 py-3 text-sm text-gray-500">
              <span className="animate-pulse">{companion.emoji} …</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 bg-gray-900 px-6 py-4">
        <div className="flex gap-3 max-w-3xl mx-auto">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Parle à ${companion.name}…`}
            rows={1}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm resize-none focus:outline-none focus:border-luna-600 placeholder-gray-600"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="px-4 py-2 bg-luna-600 hover:bg-luna-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-sm font-medium transition-colors"
          >
            Envoyer
          </button>
        </div>
        <p className="text-center text-xs text-gray-700 mt-2">Entrée pour envoyer · Maj+Entrée pour nouvelle ligne</p>
      </div>
    </div>
  )
}
