'use client';

import { useTaskStore } from '@/stores/taskStore';

export default function FontOptions() {
  const { params, updateParams } = useTaskStore();

  const font = params.font || {
    fallback_font: 'Noto Sans CJK SC',
    embed_fonts: true,
    preserve_size: true,
  };

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
          checked={font.preserve_size}
          onChange={(e) =>
            updateParams({ font: { ...font, preserve_size: e.target.checked } })
          }
          className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <span className="text-sm text-gray-600">Preserve original font size</span>
      </label>
      <div>
        <label className="block text-xs text-gray-500 mb-1">CJK Fallback Font</label>
        <input
          type="text"
          value={font.fallback_font}
          onChange={(e) =>
            updateParams({ font: { ...font, fallback_font: e.target.value } })
          }
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
      </div>
    </div>
  );
}
