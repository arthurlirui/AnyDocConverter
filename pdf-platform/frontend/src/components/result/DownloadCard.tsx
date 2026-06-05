'use client';

import { Download, RotateCcw, CheckCircle2, FileText } from 'lucide-react';
import { getDownloadUrl } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useTaskStore } from '@/stores/taskStore';

interface DownloadCardProps {
  fileId: string;
  fileName: string;
  fileSize: number;
  targetFormat: string;
  taskId: string;
}

export default function DownloadCard({
  fileId,
  fileName,
  fileSize,
  targetFormat,
  taskId,
}: DownloadCardProps) {
  const router = useRouter();
  const { reset } = useTaskStore();

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const downloadUrl = getDownloadUrl(fileId);
  const outputName = fileName.replace(/\.[^.]+$/, `.${targetFormat}`);

  const handleNewConversion = () => {
    reset();
    router.push('/');
  };

  return (
    <div className="max-w-lg mx-auto space-y-6">
      {/* Success banner */}
      <div className="bg-green-50 border border-green-200 rounded-2xl p-6 text-center">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
          <CheckCircle2 className="w-8 h-8 text-green-600" />
        </div>
        <h2 className="text-xl font-bold text-gray-800">Conversion Complete</h2>
        <p className="text-sm text-gray-500 mt-1">
          Your file has been successfully converted
        </p>
      </div>

      {/* File info card */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-primary-100 rounded-xl flex items-center justify-center">
            <FileText className="w-5 h-5 text-primary-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-800 truncate">{outputName}</p>
            <p className="text-xs text-gray-400">
              {targetFormat.toUpperCase()} &middot; {formatFileSize(fileSize)}
            </p>
          </div>
        </div>

        {/* Download button */}
        <a
          href={downloadUrl}
          download={outputName}
          className="w-full flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-700 text-white font-semibold py-3 px-6 rounded-xl transition-colors"
        >
          <Download className="w-5 h-5" />
          Download {targetFormat.toUpperCase()}
        </a>

        {/* File details */}
        <div className="mt-4 grid grid-cols-2 gap-3 text-center text-sm">
          <div className="bg-gray-50 rounded-lg p-2">
            <p className="text-gray-500">Original</p>
            <p className="font-medium text-gray-700 truncate">{fileName}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-2">
            <p className="text-gray-500">Format</p>
            <p className="font-medium text-gray-700">{targetFormat.toUpperCase()}</p>
          </div>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        <a
          href={downloadUrl}
          download={outputName}
          className="flex-1 flex items-center justify-center gap-2 bg-white border-2 border-gray-200 hover:border-gray-300 text-gray-700 font-medium py-2.5 px-4 rounded-xl transition-colors"
        >
          <Download className="w-4 h-4" />
          Save
        </a>
        <button
          onClick={handleNewConversion}
          className="flex-1 flex items-center justify-center gap-2 bg-white border-2 border-gray-200 hover:border-gray-300 text-gray-700 font-medium py-2.5 px-4 rounded-xl transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          Convert Again
        </button>
      </div>
    </div>
  );
}
