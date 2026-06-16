'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'

export default function Home() {
  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'error'>('checking')
  const [apiMessage, setApiMessage] = useState('')

  useEffect(() => {
    // Check API connection
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/health`)
      .then(res => res.json())
      .then(data => {
        setApiStatus('connected')
        setApiMessage(`API Status: ${data.status}, DB: ${data.database}`)
      })
      .catch(err => {
        setApiStatus('error')
        setApiMessage(`Failed to connect to API: ${err.message}`)
      })
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-4xl mx-auto">
        <header className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            CAiS Command Center
          </h1>
          <p className="text-xl text-gray-600">
            Your Personal AI Business Intelligence System
          </p>
        </header>

        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <h2 className="text-2xl font-semibold mb-4">System Status</h2>

          <div className="flex items-center gap-3 mb-4">
            <div className={`w-3 h-3 rounded-full ${
              apiStatus === 'connected' ? 'bg-green-500' :
              apiStatus === 'error' ? 'bg-red-500' : 'bg-yellow-500'
            }`} />
            <span className="text-gray-700">
              {apiStatus === 'checking' && 'Checking API connection...'}
              {apiStatus === 'connected' && 'Connected to backend'}
              {apiStatus === 'error' && 'Backend connection failed'}
            </span>
          </div>

          {apiMessage && (
            <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
              {apiMessage}
            </p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <h2 className="text-2xl font-semibold mb-6">Features</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Link href="/chat" className="block p-6 border-2 border-blue-500 bg-blue-50 rounded-lg hover:border-blue-600 hover:shadow-md transition-all">
              <div className="text-4xl mb-3">💬</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">AI Chat Assistant</h3>
              <p className="text-gray-600">
                Ask questions about your journal history OR brain dump what happened today. The system auto-detects and extracts insights.
              </p>
              <span className="text-xs text-blue-600 mt-2 block font-medium">✨ NEW!</span>
            </Link>

            <Link href="/journal" className="block p-6 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition-all">
              <div className="text-4xl mb-3">📝</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Journal Entries</h3>
              <p className="text-gray-600">
                Capture your business journey with journal entries. AI extracts people, tasks, insights, and more automatically.
              </p>
            </Link>

            <div className="p-6 border-2 border-gray-200 rounded-lg opacity-60">
              <div className="text-4xl mb-3">👥</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">People Tracking</h3>
              <p className="text-gray-600">
                Track relationships and see all mentions of people across your journey.
              </p>
              <span className="text-xs text-gray-500 mt-2 block">Coming in Phase 5</span>
            </div>

            <div className="p-6 border-2 border-gray-200 rounded-lg opacity-60">
              <div className="text-4xl mb-3">📊</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Dashboard</h3>
              <p className="text-gray-600">
                Visualize your journey with timelines, stats, and insights.
              </p>
              <span className="text-xs text-gray-500 mt-2 block">Coming in Phase 6</span>
            </div>
          </div>
        </div>

        {apiStatus === 'connected' && (
          <div className="text-center space-x-4">
            <Link
              href="/chat"
              className="inline-block bg-blue-600 text-white px-8 py-4 rounded-lg hover:bg-blue-700 font-semibold text-lg shadow-lg hover:shadow-xl transition-all"
            >
              Start Chatting with Your AI Assistant →
            </Link>
            <Link
              href="/journal/new"
              className="inline-block bg-white text-blue-600 border-2 border-blue-600 px-8 py-4 rounded-lg hover:bg-blue-50 font-semibold text-lg shadow-lg hover:shadow-xl transition-all"
            >
              Or Create a Journal Entry
            </Link>
          </div>
        )}

        <div className="mt-8 text-center text-gray-500 text-sm">
          <p>Built with FastAPI, PostgreSQL, Next.js, and Claude AI</p>
        </div>
      </div>
    </div>
  )
}
