import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'

const nav = [
  { to: '/dashboard', label: 'Dashboard',   icon: '📊' },
  { to: '/chat',      label: 'Chat',         icon: '💬' },
  { to: '/memories',  label: 'Mémoires',     icon: '🧠' },
  { to: '/training',  label: 'Entraînement', icon: '🎓' },
]

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col py-6 px-3 gap-1 shrink-0">
        <div className="px-3 mb-6">
          <span className="text-2xl font-bold text-luna-500">🌙 Luna</span>
          <p className="text-xs text-gray-500 mt-0.5">Admin Dashboard</p>
        </div>
        {nav.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-luna-700/30 text-luna-400'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
              }`
            }
          >
            <span>{icon}</span>
            {label}
          </NavLink>
        ))}
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  )
}
