'use client';

import { useTaskStore } from '@/stores/taskStore';
import OCROptions from './OCROptions';
import LayoutOptions from './LayoutOptions';
import ImageQualityOptions from './ImageQualityOptions';
import FontOptions from './FontOptions';
import { ChevronDown, ChevronUp, Settings2 } from 'lucide-react';
import { useState } from 'react';

export default function ParamsPanel() {
  const { targetFormat, paramsDefaults } = useTaskStore();
  const [expanded, setExpanded] = useState(false);

  if (!paramsDefaults) return null;

  const hasOptions = paramsDefaults.ocr || paramsDefaults.layout;
  const hasImageOptions = paramsDefaults.imageQuality;
  const hasFontOptions = paramsDefaults.font;

  if (!hasOptions && !hasImageOptions && !hasFontOptions) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Settings2 className="w-4 h-4 text-gray-500" />
          <span className="font-medium text-gray-700 text-sm">
            Conversion Options
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-6 border-t border-gray-100 pt-4">
          {hasOptions && (
            <div className="space-y-4">
              {paramsDefaults.ocr && <OCROptions />}
              {paramsDefaults.layout && <LayoutOptions />}
            </div>
          )}

          {hasImageOptions && (
            <div>
              {hasOptions && (
                <hr className="border-gray-100 mb-4" />
              )}
              <ImageQualityOptions />
            </div>
          )}

          {hasFontOptions && (
            <div>
              {(hasOptions || hasImageOptions) && (
                <hr className="border-gray-100 mb-4" />
              )}
              <FontOptions />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
