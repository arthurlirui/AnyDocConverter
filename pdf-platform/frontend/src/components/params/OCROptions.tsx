'use client';

import { useTaskStore } from '@/stores/taskStore';

export default function OCROptions() {
  const { params, updateParams } = useTaskStore();

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-gray-700">OCR Settings</h4>
      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={params.ocrEnabled}
          onChange={(e) => updateParams({ ocrEnabled: e.target.checked })}
          className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <span className="text-sm text-gray-600">Enable OCR (text recognition)</span>
      </label>

      {params.ocrEnabled && (
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            OCR Language
          </label>
          <select
            value={params.ocrLanguage}
            onChange={(e) => updateParams({ ocrLanguage: e.target.value })}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="eng">English</option>
            <option value="chi_sim">Chinese (Simplified)</option>
            <option value="chi_tra">Chinese (Traditional)</option>
            <option value="jpn">Japanese</option>
            <option value="kor">Korean</option>
            <option value="fra">French</option>
            <option value="deu">German</option>
            <option value="spa">Spanish</option>
            <option value="rus">Russian</option>
            <option value="ara">Arabic</option>
          </select>
        </div>
      )}
    </div>
  );
}
