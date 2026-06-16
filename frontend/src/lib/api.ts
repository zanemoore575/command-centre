const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface JournalEntry {
  id: number
  content: string
  entry_date: string
  created_at: string
  updated_at: string
  entry_type?: string
  mood?: string
  energy_level?: number
  is_processed: boolean
  metadata?: any
}

export interface Person {
  id: number
  name: string
  company?: string
  role?: string
  email?: string
  phone?: string
  first_mentioned_at?: string
  last_mentioned_at?: string
  mention_count: number
  relationship_status?: string
  notes?: string
  metadata?: any
}

export interface Commitment {
  id: number
  journal_entry_id: number
  person_id?: number
  description: string
  due_date?: string
  status: string
  priority: string
  completed_at?: string
}

export interface PainPoint {
  id: number
  journal_entry_id: number
  person_id?: number
  description: string
  category?: string
  severity: string
  frequency_mentioned: number
  validation_status: string
}

// Generic fetcher for SWR
export async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`)

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`)
  }

  return res.json()
}

// Journal Entry API
export async function createJournalEntry(data: {
  content: string
  entry_date: string
  entry_type?: string
  mood?: string
  energy_level?: number
}): Promise<JournalEntry> {
  const res = await fetch(`${API_BASE}/api/journal/entries`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })

  if (!res.ok) {
    throw new Error(`Failed to create entry: ${res.status}`)
  }

  return res.json()
}

export async function updateJournalEntry(id: number, data: Partial<JournalEntry>): Promise<JournalEntry> {
  const res = await fetch(`${API_BASE}/api/journal/entries/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })

  if (!res.ok) {
    throw new Error(`Failed to update entry: ${res.status}`)
  }

  return res.json()
}

export async function deleteJournalEntry(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/journal/entries/${id}`, {
    method: 'DELETE',
  })

  if (!res.ok) {
    throw new Error(`Failed to delete entry: ${res.status}`)
  }
}

// People API
export async function updatePerson(id: number, data: Partial<Person>): Promise<Person> {
  const res = await fetch(`${API_BASE}/api/people/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })

  if (!res.ok) {
    throw new Error(`Failed to update person: ${res.status}`)
  }

  return res.json()
}

// Commitment API
export async function updateCommitment(id: number, data: Partial<Commitment>): Promise<Commitment> {
  const res = await fetch(`${API_BASE}/api/commitments/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })

  if (!res.ok) {
    throw new Error(`Failed to update commitment: ${res.status}`)
  }

  return res.json()
}
