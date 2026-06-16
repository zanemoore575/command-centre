'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface JournalEntryFormProps {
  initialData?: {
    content: string;
    entry_date: string;
    entry_type?: string;
    mood?: string;
    energy_level?: number;
  };
  onSubmit: (data: {
    content: string;
    entry_date: string;
    entry_type?: string;
    mood?: string;
    energy_level?: number;
  }) => Promise<void>;
  onCancel?: () => void;
  submitLabel?: string;
}

export default function JournalEntryForm({
  initialData,
  onSubmit,
  onCancel,
  submitLabel = 'Create Entry'
}: JournalEntryFormProps) {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [content, setContent] = useState(initialData?.content || '');
  const [entryDate, setEntryDate] = useState(
    initialData?.entry_date || new Date().toISOString().split('T')[0]
  );
  const [entryType, setEntryType] = useState(initialData?.entry_type || 'reflection');
  const [mood, setMood] = useState(initialData?.mood || '');
  const [energyLevel, setEnergyLevel] = useState<number | undefined>(initialData?.energy_level);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await onSubmit({
        content,
        entry_date: entryDate,
        entry_type: entryType,
        mood: mood || undefined,
        energy_level: energyLevel
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save entry');
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Entry Date */}
      <div>
        <label htmlFor="entry_date" className="block text-sm font-medium text-gray-700 mb-1">
          Entry Date
        </label>
        <input
          type="date"
          id="entry_date"
          value={entryDate}
          onChange={(e) => setEntryDate(e.target.value)}
          required
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Content */}
      <div>
        <label htmlFor="content" className="block text-sm font-medium text-gray-700 mb-1">
          Journal Entry
        </label>
        <textarea
          id="content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          required
          rows={12}
          placeholder="What happened today? Any customer calls, insights, or important moments..."
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
        />
        <p className="text-sm text-gray-500 mt-1">
          The AI will automatically extract people, commitments, and pain points from your entry.
        </p>
      </div>

      {/* Entry Type */}
      <div>
        <label htmlFor="entry_type" className="block text-sm font-medium text-gray-700 mb-1">
          Entry Type
        </label>
        <select
          id="entry_type"
          value={entryType}
          onChange={(e) => setEntryType(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="reflection">Reflection</option>
          <option value="meeting">Meeting</option>
          <option value="insight">Insight</option>
          <option value="customer_call">Customer Call</option>
          <option value="decision">Decision</option>
        </select>
      </div>

      {/* Mood (Optional) */}
      <div>
        <label htmlFor="mood" className="block text-sm font-medium text-gray-700 mb-1">
          Mood (Optional)
        </label>
        <select
          id="mood"
          value={mood}
          onChange={(e) => setMood(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">-- Not specified --</option>
          <option value="excited">Excited</option>
          <option value="productive">Productive</option>
          <option value="neutral">Neutral</option>
          <option value="frustrated">Frustrated</option>
          <option value="uncertain">Uncertain</option>
          <option value="confident">Confident</option>
        </select>
      </div>

      {/* Energy Level (Optional) */}
      <div>
        <label htmlFor="energy_level" className="block text-sm font-medium text-gray-700 mb-1">
          Energy Level (Optional)
        </label>
        <div className="flex items-center gap-4">
          {[1, 2, 3, 4, 5].map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => setEnergyLevel(level)}
              className={`w-12 h-12 rounded-full border-2 transition-colors ${
                energyLevel === level
                  ? 'bg-blue-500 text-white border-blue-500'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-blue-300'
              }`}
            >
              {level}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setEnergyLevel(undefined)}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Clear
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-1">1 = Low energy, 5 = High energy</p>
      </div>

      {/* Actions */}
      <div className="flex gap-3 pt-4">
        <button
          type="submit"
          disabled={isSubmitting || !content.trim()}
          className="flex-1 bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium transition-colors"
        >
          {isSubmitting ? 'Saving...' : submitLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-6 py-3 border border-gray-300 rounded-md hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
