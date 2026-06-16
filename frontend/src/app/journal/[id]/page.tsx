'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useJournalEntry, useDeleteJournalEntry } from '@/hooks/useJournal';
import { useState, useEffect } from 'react';
import ExtractedEntities from '@/components/journal/ExtractedEntities';

export default function JournalEntryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const entryId = params.id as string;
  const { entry, isLoading, isError } = useJournalEntry(entryId);
  const deleteEntry = useDeleteJournalEntry();
  const [isDeleting, setIsDeleting] = useState(false);
  const [entities, setEntities] = useState<any>(null);
  const [loadingEntities, setLoadingEntities] = useState(false);

  // Fetch extracted entities
  useEffect(() => {
    if (!entry) return;

    const fetchEntities = async () => {
      setLoadingEntities(true);
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/journal/entries/${entryId}/entities`
        );
        if (response.ok) {
          const data = await response.json();
          setEntities(data);
        }
      } catch (error) {
        console.error('Failed to load entities:', error);
      } finally {
        setLoadingEntities(false);
      }
    };

    fetchEntities();
  }, [entry, entryId]);

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this entry? This cannot be undone.')) {
      return;
    }

    setIsDeleting(true);
    try {
      await deleteEntry(parseInt(entryId));
      router.push('/journal');
    } catch (error) {
      alert('Failed to delete entry');
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="text-gray-600 mt-4">Loading entry...</p>
          </div>
        </div>
      </div>
    );
  }

  if (isError || !entry) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="bg-red-50 border border-red-200 text-red-800 px-6 py-4 rounded-lg">
            Entry not found or failed to load.
          </div>
          <Link
            href="/journal"
            className="inline-block mt-4 text-blue-600 hover:text-blue-800"
          >
            ← Back to Journal
          </Link>
        </div>
      </div>
    );
  }

  const formattedDate = new Date(entry.entry_date).toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });

  const getTypeColor = (type?: string) => {
    switch (type) {
      case 'meeting': return 'bg-purple-100 text-purple-800';
      case 'insight': return 'bg-yellow-100 text-yellow-800';
      case 'customer_call': return 'bg-green-100 text-green-800';
      case 'decision': return 'bg-red-100 text-red-800';
      default: return 'bg-blue-100 text-blue-800';
    }
  };

  const getMoodEmoji = (mood?: string) => {
    switch (mood) {
      case 'excited': return '🚀';
      case 'productive': return '✅';
      case 'neutral': return '😐';
      case 'frustrated': return '😤';
      case 'uncertain': return '🤔';
      case 'confident': return '💪';
      default: return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Back Link */}
        <Link
          href="/journal"
          className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-6"
        >
          ← Back to Journal
        </Link>

        {/* Main Content */}
        <div className="bg-white rounded-lg shadow-sm p-8">
          {/* Header */}
          <div className="border-b border-gray-200 pb-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h1 className="text-2xl font-bold text-gray-900 mb-2">{formattedDate}</h1>
                <div className="flex items-center gap-3">
                  <span className={`text-sm px-3 py-1 rounded-full ${getTypeColor(entry.entry_type)}`}>
                    {entry.entry_type || 'reflection'}
                  </span>
                  {entry.mood && (
                    <span className="text-sm px-3 py-1 bg-gray-100 text-gray-700 rounded-full">
                      {getMoodEmoji(entry.mood)} {entry.mood}
                    </span>
                  )}
                  {entry.energy_level && (
                    <span className="text-sm px-3 py-1 bg-gray-100 text-gray-700 rounded-full">
                      Energy: {entry.energy_level}/5
                    </span>
                  )}
                  {entry.is_processed && (
                    <span className="text-sm text-green-600 font-medium">✓ Processed</span>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <Link
                  href={`/journal/${entry.id}/edit`}
                  className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                >
                  Edit
                </Link>
                <button
                  onClick={handleDelete}
                  disabled={isDeleting}
                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  {isDeleting ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="prose prose-gray max-w-none">
            <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">
              {entry.content}
            </div>
          </div>

          {/* Metadata */}
          <div className="border-t border-gray-200 mt-8 pt-6">
            <div className="grid grid-cols-2 gap-4 text-sm text-gray-600">
              <div>
                <span className="font-medium">Created:</span>{' '}
                {new Date(entry.created_at).toLocaleString()}
              </div>
              <div>
                <span className="font-medium">Last Updated:</span>{' '}
                {new Date(entry.updated_at).toLocaleString()}
              </div>
            </div>
          </div>

          {/* Extracted Entities */}
          {entities && (
            <ExtractedEntities
              people={entities.people || []}
              tasks={entities.tasks || []}
              topics={entities.topics || []}
              insights={entities.insights || []}
              events={entities.events || []}
              challenges={entities.challenges || []}
              wins={entities.wins || []}
              isProcessed={entry.is_processed}
            />
          )}
        </div>
      </div>
    </div>
  );
}
