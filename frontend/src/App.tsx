import React, { useEffect, useState } from 'react'
import { apiFetch } from './lib/api'
import { formatHealthStatus } from './utils/health'

function App() {
  const [status, setStatus] = useState('Checking...')

  useEffect(() => {
    apiFetch('/api/health')
      .then(res => res.json())
      .then(data => {
        const health = formatHealthStatus(data.services || {})
        setStatus(health.overall)
      })
      .catch(() => setStatus('unreachable'))
  }, [])

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col items-center justify-center">
      <h1 className="text-4xl font-bold tracking-tight">MemMesh</h1>
      <p className="mt-4 text-slate-400">Scaffolded React + Vite + TypeScript application.</p>
      <p id="system-status" className="mt-2 text-green-400">System status: {status}</p>
    </div>
  )
}

export default App
