'use client';

import { useTaskStore } from '@/stores/taskStore';

export default function LayoutOptions() {
  const { params, updateParams } = useTaskStore();

  const layout = params.layout || {
    preservation: 'exact',
    detect_tables: true,
    detect_images: true,
    detect_headers_footers: true,
    reading_order: true,
  };

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-gray-700">Layout Settings</h4>

      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={layout.detect_tables}
          onChange={(e) =>
            updateParams({ layout: { ...layout, detect_tables: e.target.checked } })
          }
          className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <span className="text-sm text-gray-600">Detect tables</span>
      </label>

      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={layout.detect_images}
          onChange={(e) =>
            updateParams({ layout: { ...layout, detect_images: e.target.checked } })
          }
          className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <span className="text-sm text-gray-600">Extract images</span>
      </label>

      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={layout.reading_order}
          onChange={(e) =>
            updateParams({ layout: { ...layout, reading_order: e.target.checked } })
          }
          className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <span className="text-sm text-gray-600">Restore reading order</span>
      </label>
    </div>
  );
}
