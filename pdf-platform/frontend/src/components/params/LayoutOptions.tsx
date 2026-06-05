'use client';

import { useTaskStore } from '@/stores/taskStore';

const PAGE_SIZES = ['A3', 'A4', 'A5', 'Letter', 'Legal', 'Tabloid'];
const MARGIN_OPTIONS = ['none', 'narrow', 'normal', 'wide'];

export default function LayoutOptions() {
  const { params, updateParams } = useTaskStore();

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-gray-700">Layout Settings</h4>

      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={params.keepLayout}
          onChange={(e) => updateParams({ keepLayout: e.target.checked })}
          className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <span className="text-sm text-gray-600">Keep original layout</span>
      </label>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Page Size</label>
          <select
            value={params.pageSize}
            onChange={(e) => updateParams({ pageSize: e.target.value })}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">Margins</label>
          <select
            value={params.margins}
            onChange={(e) => updateParams({ margins: e.target.value })}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            {MARGIN_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m.charAt(0).toUpperCase() + m.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
