'use client';

import { useTaskStore } from '@/stores/taskStore';

export default function FontOptions() {
  const { params, updateParams } = useTaskStore();

  const font = params.font || { fallback_font: 'NotoSansCJK', embed_fonts: true, subset_fonts: true, mode: 'approximate' };

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-gray-700">Font Settings</h4>
      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={font.embed_fonts}
          onChange={(e) =>
            updateParams({ font: { ...font, embed_fonts: e.target.checked } })
          }
          className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <span className="text-sm text-gray-600">Embed fonts in output</span>
      </label>
      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={font.subset_fonts}
          onChange={(e) =>
            updateParams({ font: { ...font, subset_fonts: e.target.checked } })
          }
          className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <span className="text-sm text-gray-600">
          Subset fonts (smaller file size)
        </span>
      </label>
    </div>
  );
}
