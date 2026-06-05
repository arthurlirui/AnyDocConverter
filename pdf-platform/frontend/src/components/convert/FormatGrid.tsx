'use client';

import { useEffect, useState } from 'react';
import { useTaskStore } from '@/stores/taskStore';
import { fetchFormats } from '@/lib/api';
import clsx from 'clsx';

interface FormatItem {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  group: string;
}

interface FormatGroup {
  name: string;
  formats: FormatItem[];
}

const DEFAULT_ICONS: Record<string, string> = {
  pdf: '📄',
  word: '📝',
  excel: '📊',
  ppt: '📽️',
  image: '🖼️',
  txt: '📃',
  html: '🌐',
  epub: '📚',
};

const GROUPS: Record<string, string> = {
  document: 'Document Formats',
  image: 'Image Formats',
  ebook: 'eBook Formats',
  data: 'Data Formats',
};

export default function FormatGrid() {
  const { targetFormat, selectFormat, loadFormatParams } = useTaskStore();
  const [groups, setGroups] = useState<FormatGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchFormats();
        // Group formats
        const groupMap = new Map<string, FormatItem[]>();
        const formatList = Array.isArray(data) ? data : data.formats;
        for (const fmt of formatList) {
          const key = (fmt as any).group || 'document';
          if (!groupMap.has(key)) groupMap.set(key, []);
          groupMap.get(key)!.push(fmt);
        }
        const grouped: FormatGroup[] = [];
        for (const [key, items] of groupMap.entries()) {
          grouped.push({
            name: GROUPS[key] || key.charAt(0).toUpperCase() + key.slice(1),
            formats: items,
          });
        }
        setGroups(grouped);
      } catch (e: any) {
        setError(e.message || 'Failed to load formats');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleSelect = async (formatId: string) => {
    selectFormat(formatId);
    await loadFormatParams(formatId);
  };

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <div className="animate-pulse text-gray-400">Loading formats...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8 text-red-500">
        <p>Failed to load formats</p>
        <p className="text-sm text-gray-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {groups.map((group) => (
        <div key={group.name}>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {group.name}
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {group.formats.map((fmt) => {
              const isSelected = targetFormat === fmt.id;
              return (
                <button
                  key={fmt.id}
                  onClick={() => handleSelect(fmt.id)}
                  className={clsx(
                    'flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-150',
                    isSelected
                      ? 'border-primary-500 bg-primary-50 shadow-sm'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  )}
                >
                  <span className="text-3xl">
                    {fmt.icon || DEFAULT_ICONS[fmt.id.split('-')[0]] || '📄'}
                  </span>
                  <span
                    className={clsx(
                      'text-sm font-semibold',
                      isSelected ? 'text-primary-700' : 'text-gray-700'
                    )}
                  >
                    {fmt.name}
                  </span>
                  <span className="text-xs text-gray-400 text-center leading-tight">
                    {fmt.description}
                  </span>
                  {isSelected && (
                    <span className="mt-1 text-xs font-medium text-primary-600">
                      ✓ Selected
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
