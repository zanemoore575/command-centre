'use client';

import { useRouter } from 'next/navigation';
import JournalEntryForm from '@/components/journal/JournalEntryForm';
import { useCreateJournalEntry } from '@/hooks/useJournal';

export default function NewJournalEntryPage() {
  const router = useRouter();
  const createEntry = useCreateJournalEntry();

  const handleSubmit = async (data: {
    content: string;
    entry_date: string;
    entry_type?: string;
    mood?: string;
    energy_level?: number;
  }) => {
    await createEntry(data);
    router.push('/journal');
  };

  const handleCancel = () => {
    router.push('/journal');
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">New Journal Entry</h1>
          <p className="text-gray-600 mt-2">
            Capture your thoughts, customer conversations, and insights. AI will automatically
            extract people, commitments, and pain points.
          </p>
        </div>

        {/* Form */}
        <div className="bg-white rounded-lg shadow-sm p-8">
          <JournalEntryForm
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            submitLabel="Create Entry"
          />
        </div>
      </div>
    </div>
  );
}
