import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import Memories from './pages/Memories'
import Training from './pages/Training'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/"          element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/chat"      element={<Chat />} />
        <Route path="/memories"  element={<Memories />} />
        <Route path="/training"  element={<Training />} />
      </Routes>
    </Layout>
  )
}
