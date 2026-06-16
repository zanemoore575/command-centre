'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useJournalEntry, useUpdateJournalEntry } from '@/hooks/useJournal';
import JournalEntryForm from '@/components/journal/JournalEntryForm';

export default function EditJournalEntryPage() {
  const params = useParams();
  const router = useRouter();
  const entryId = params.id as string;
  const { entry, isLoading, isError } = useJournalEntry(entryId);
  const updateEntry = useUpdateJournalEntry();

  const handleSubmit = async (data: {
    content: string;
    entry_date: string;
    entry_type?: string;
    mood?: string;
    energy_level?: number;
  }) => {
    await updateEntry(parseInt(entryId), data);
    router.push(`/journal/${entryId}`);
  };

  const handleCancel = () => {
    router.push(`/journal/${entryId}`);
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

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Back Link */}
        <Link
          href={`/journal/${entryId}`}
          className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-6"
        >
          ← Back to Entry
        </Link>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Edit Journal Entry</h1>
          <p className="text-gray-600 mt-2">
            Make changes to your entry. Re-extraction will run automatically if content changes.
          </p>
        </div>

        {/* Form */}
        <div className="bg-white rounded-lg shadow-sm p-8">
          <JournalEntryForm
            initialData={{
              content: entry.content,
              entry_date: entry.entry_date,
              entry_type: entry.entry_type,
              mood: entry.mood || undefined,
              energy_level: entry.energy_level || undefined
            }}
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            submitLabel="Save Changes"
          />
        </div>
      </div>
    </div>
  );
}
