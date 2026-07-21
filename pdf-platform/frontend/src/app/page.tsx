'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTaskStore } from '@/stores/taskStore';
import FileUploader from '@/components/upload/FileUploader';
import FormatGrid from '@/components/convert/FormatGrid';
import ParamsPanel from '@/components/params/ParamsPanel';
import { ArrowRight, Loader2 } from 'lucide-react';

export default function HomePage() {
  const router = useRouter();
  const {
    file,
    fileId,
    isUploading,
    targetFormat,
    createAndStartTask,
  } = useTaskStore();
  const [starting, setStarting] = useState(false);

  const canConvert = fileId && targetFormat && !isUploading;

  const handleStartConversion = async () => {
    if (!canConvert) return;
    setStarting(true);
    const taskId = await createAndStartTask();
    if (taskId) {
      router.push(`/convert/${taskId}`);
    }
    setStarting(false);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
      {/* Hero */}
      <div className="text-center mb-10">
        <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-3">
          Convert your PDF files
        </h1>
        <p className="text-gray-500 max-w-lg mx-auto">
          Upload your PDF and convert it to Word, Excel, PPT, Images, and more.
          Fast, secure, and free.
        </p>
      </div>

      {/* Upload */}
      <section className="mb-10">
        <FileUploader />
      </section>

      {/* Format selection — only show after upload */}
      {fileId && (
        <>
          <section className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-6 h-6 bg-primary-100 rounded-full flex items-center justify-center">
                <span className="text-xs font-bold text-primary-600">2</span>
              </div>
              <h2 className="text-lg font-semibold text-gray-800">
                Select target format
              </h2>
            </div>
            <FormatGrid />
          </section>

          {/* Params */}
          <section className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-6 h-6 bg-primary-100 rounded-full flex items-center justify-center">
                <span className="text-xs font-bold text-primary-600">3</span>
              </div>
              <h2 className="text-lg font-semibold text-gray-800">
                Adjust settings (optional)
              </h2>
            </div>
            <ParamsPanel />
          </section>

          {/* Convert button */}
          <section className="text-center">
            <button
              onClick={handleStartConversion}
              disabled={!canConvert || starting}
              className="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-3.5 px-8 rounded-xl text-lg transition-colors shadow-sm"
            >
              {starting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  Start Conversion
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
            {!targetFormat && fileId && (
              <p className="text-sm text-gray-400 mt-2">
                Please select a target format above
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
