'use client';

import { FileText, Download, ArrowLeftRight, CheckCircle2 } from 'lucide-react';

interface PreviewCompareProps {
  fileName: string;
  fileSize: number;
  targetFormat: string;
}

export default function PreviewCompare({
  fileName,
  fileSize,
  targetFormat,
}: PreviewCompareProps) {
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const sourceExt = fileName.split('.').pop()?.toUpperCase() || 'PDF';

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-6">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
        Conversion Summary
      </h3>

      <div className="flex items-center justify-center gap-4 sm:gap-8">
        {/* Source */}
        <div className="flex flex-col items-center text-center">
          <div className="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center mb-2">
            <FileText className="w-8 h-8 text-primary-600" />
          </div>
          <span className="text-sm font-medium text-gray-700">{sourceExt}</span>
          <span className="text-xs text-gray-400">
            {formatFileSize(fileSize)}
          </span>
        </div>

        {/* Arrow */}
        <div className="flex flex-col items-center">
          <ArrowLeftRight className="w-6 h-6 text-primary-500 mb-1" />
          <CheckCircle2 className="w-4 h-4 text-green-500" />
        </div>

        {/* Target */}
        <div className="flex flex-col items-center text-center">
          <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mb-2">
            <FileText className="w-8 h-8 text-green-600" />
          </div>
          <span className="text-sm font-medium text-gray-700">
            {targetFormat.toUpperCase()}
          </span>
          <span className="text-xs text-green-500 font-medium">Ready</span>
        </div>
      </div>
    </div>
  );
}
