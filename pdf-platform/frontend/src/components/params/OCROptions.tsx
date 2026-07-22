'use client';

import { useTaskStore } from '@/stores/taskStore';

export default function OCROptions() {
  const { params, updateParams, targetFormat } = useTaskStore();

  const ocr = params.ocr || {
    enabled: false,
    engine: 'paddle',
    language: 'ch',
    min_confidence: 0.45,
    enhance_image: false,
    enhance_mode: 'standard',
    upscale_factor: 1.0,
    contrast: 1.15,
    sharpness: 1.05,
    binarize: false,
  };

  const usefulForText = targetFormat === 'txt' || targetFormat === 'markdown' || targetFormat === 'docx';
  const hardMode = ocr.enhance_mode === 'hard';

  const updateOCR = (patch: Partial<typeof ocr>) => {
    updateParams({
      ocr: {
        ...ocr,
        engine: 'paddle',
        ...patch,
      },
    });
  };

  return (
    <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-4 space-y-4">
      <div>
        <h4 className="text-sm font-semibold text-gray-800">OCR Text Recognition</h4>
        <p className="text-xs text-gray-500 mt-1">
          Use local PaddleOCR to recognize scanned PDFs, photos, screenshots, receipts, handwritten-like print, compressed images and other difficult documents, then convert them into editable text.
        </p>
        {!usefulForText && (
          <p className="text-xs text-amber-600 mt-1">
            OCR is most useful when exporting to Word, Markdown, or Plain Text.
          </p>
        )}
      </div>

      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={ocr.enabled}
          onChange={(e) => updateOCR({ enabled: e.target.checked })}
          className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
        />
        <span className="text-sm text-gray-700">Enable local PaddleOCR</span>
      </label>

      {ocr.enabled && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Recognition language
              </label>
              <select
                value={ocr.language}
                onChange={(e) => updateOCR({ language: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white"
              >
                <option value="ch">Chinese / English mixed</option>
                <option value="en">English</option>
                <option value="chinese_cht">Traditional Chinese</option>
                <option value="japan">Japanese</option>
                <option value="korean">Korean</option>
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Min confidence: {Math.round((ocr.min_confidence ?? 0.45) * 100)}%
              </label>
              <input
                type="range"
                min="0.1"
                max="0.95"
                step="0.05"
                value={ocr.min_confidence ?? 0.45}
                onChange={(e) => updateOCR({ min_confidence: Number(e.target.value) })}
                className="w-full"
              />
              <p className="text-[11px] text-gray-400 mt-1">
                Lower values keep more uncertain text; higher values reduce noise.
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white/80 p-3 space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={!!ocr.enhance_image}
                onChange={(e) =>
                  updateOCR({
                    enhance_image: e.target.checked,
                    enhance_mode: e.target.checked ? ocr.enhance_mode || 'standard' : 'standard',
                  })
                }
                className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm font-medium text-gray-700">Enhance difficult images</span>
            </label>

            {ocr.enhance_image && (
              <div className="space-y-3 pl-7">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Enhancement mode</label>
                  <select
                    value={ocr.enhance_mode || 'standard'}
                    onChange={(e) =>
                      updateOCR({
                        enhance_mode: e.target.value as 'standard' | 'hard',
                        upscale_factor: e.target.value === 'hard' ? Math.max(ocr.upscale_factor || 1, 2) : ocr.upscale_factor || 1,
                        contrast: e.target.value === 'hard' ? Math.max(ocr.contrast || 1.15, 1.6) : ocr.contrast || 1.15,
                        sharpness: e.target.value === 'hard' ? Math.max(ocr.sharpness || 1.05, 1.4) : ocr.sharpness || 1.05,
                      })
                    }
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="standard">Standard: photos / screenshots / receipts</option>
                    <option value="hard">Hard: low contrast / tiny text / noisy scans</option>
                  </select>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">
                      Upscale: {(ocr.upscale_factor ?? 1).toFixed(1)}x
                    </label>
                    <input
                      type="range"
                      min="1"
                      max="4"
                      step="0.5"
                      value={ocr.upscale_factor ?? (hardMode ? 2 : 1)}
                      onChange={(e) => updateOCR({ upscale_factor: Number(e.target.value) })}
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">
                      Contrast: {(ocr.contrast ?? 1.15).toFixed(2)}x
                    </label>
                    <input
                      type="range"
                      min="0.8"
                      max="3"
                      step="0.05"
                      value={ocr.contrast ?? (hardMode ? 1.6 : 1.15)}
                      onChange={(e) => updateOCR({ contrast: Number(e.target.value) })}
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">
                      Sharpness: {(ocr.sharpness ?? 1.05).toFixed(2)}x
                    </label>
                    <input
                      type="range"
                      min="0.8"
                      max="3"
                      step="0.05"
                      value={ocr.sharpness ?? (hardMode ? 1.4 : 1.05)}
                      onChange={(e) => updateOCR({ sharpness: Number(e.target.value) })}
                      className="w-full"
                    />
                  </div>
                </div>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!ocr.binarize}
                    onChange={(e) => updateOCR({ binarize: e.target.checked })}
                    className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-xs text-gray-600">
                    Binarize before OCR — useful for faint scans, may hurt colorful photos.
                  </span>
                </label>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
