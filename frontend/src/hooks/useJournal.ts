import useSWR from 'swr';
import { fetcher, createJournalEntry, updateJournalEntry, deleteJournalEntry, JournalEntry } from '@/lib/api';

interface JournalEntryListResponse {
  entries: JournalEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export function useJournalEntries(page: number = 1, pageSize: number = 20) {
  const { data, error, mutate } = useSWR<JournalEntryListResponse>(
    `/api/journal/entries?page=${page}&page_size=${pageSize}`,
    fetcher
  );

  return {
    entries: data?.entries || [],
    total: data?.total || 0,
    page: data?.page || 1,
    pageSize: data?.page_size || pageSize,
    totalPages: data?.total_pages || 1,
    isLoading: !error && !data,
    isError: error,
    mutate
  };
}

export function useJournalEntry(id: string | number | null) {
  const { data, error, mutate } = useSWR<JournalEntry>(
    id ? `/api/journal/entries/${id}` : null,
    fetcher
  );

  return {
    entry: data,
    isLoading: !error && !data,
    isError: error,
    mutate
  };
}

export function useCreateJournalEntry() {
  return async (data: {
    content: string;
    entry_date: string;
    entry_type?: string;
    mood?: string;
    energy_level?: number;
  }) => {
    return await createJournalEntry(data);
  };
}

export function useUpdateJournalEntry() {
  return async (id: number, data: Partial<JournalEntry>) => {
    return await updateJournalEntry(id, data);
  };
}

export function useDeleteJournalEntry() {
  return async (id: number) => {
    return await deleteJournalEntry(id);
  };
}
