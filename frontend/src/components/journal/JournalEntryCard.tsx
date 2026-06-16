'use client';

import Link from 'next/link';
import { JournalEntry } from '@/lib/api';

interface JournalEntryCardProps {
  entry: JournalEntry;
}

export default function JournalEntryCard({ entry }: JournalEntryCardProps) {
  const formattedDate = new Date(entry.entry_date).toLocaleDateString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });

  const preview = entry.content.length > 200
    ? entry.content.substring(0, 200) + '...'
    : entry.content;

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
    <Link href={`/journal/${entry.id}`}>
      <div className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow cursor-pointer">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-gray-900">{formattedDate}</span>
            <span className={`text-xs px-2 py-1 rounded-full ${getTypeColor(entry.entry_type)}`}>
              {entry.entry_type || 'reflection'}
            </span>
            {entry.mood && (
              <span className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded-full">
                {getMoodEmoji(entry.mood)} {entry.mood}
              </span>
            )}
          </div>
          {entry.is_processed && (
            <span className="text-xs text-green-600 font-medium">✓ Processed</span>
          )}
        </div>

        {/* Content Preview */}
        <p className="text-gray-700 whitespace-pre-wrap">{preview}</p>

        {/* Footer */}
        <div className="flex items-center gap-4 mt-4 text-xs text-gray-500">
          {entry.energy_level && (
            <span>Energy: {entry.energy_level}/5</span>
          )}
          <span>Created {new Date(entry.created_at).toLocaleDateString()}</span>
        </div>
      </div>
    </Link>
  );
}
