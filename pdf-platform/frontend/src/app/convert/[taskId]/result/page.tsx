'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTaskStore } from '@/stores/taskStore';
import PreviewCompare from '@/components/preview/PreviewCompare';
import DownloadCard from '@/components/result/DownloadCard';
import { Loader2 } from 'lucide-react';

export default function ConvertResultPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.taskId as string;
  const { taskStatus, pollTask, stopPolling, phase, uploadedFileName, file } = useTaskStore();
  const fileName = taskStatus?.file_name || uploadedFileName || file?.name || 'file.pdf';
  const fileSize = taskStatus?.file_size || file?.size || 0;

  // Poll for final status if not yet loaded
  useEffect(() => {
    if (!taskStatus || phase !== 'completed') {
      const doPoll = async () => {
        await pollTask(taskId);
      };
      doPoll();
      const interval = setInterval(doPoll, 2000);
      return () => clearInterval(interval);
    }
  }, [taskId, pollTask, taskStatus, phase]);

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  // Redirect back to convert page if task not completed
  useEffect(() => {
    if (phase === 'failed' || (taskStatus && taskStatus.status === 'failed')) {
      const timer = setTimeout(() => {
        router.push(`/convert/${taskId}`);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [phase, taskStatus, taskId, router]);

  if (!taskStatus || phase !== 'completed') {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-20 text-center">
        <Loader2 className="w-10 h-10 animate-spin text-primary-600 mx-auto mb-3" />
        <p className="text-gray-500">Loading result...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Download Result</h1>
        <p className="text-gray-500 text-sm mt-1">
          Your converted file is ready for download
        </p>
      </div>

      {/* Preview / summary */}
      <section className="mb-6">
        <PreviewCompare
          fileName={fileName}
          fileSize={fileSize}
          targetFormat={taskStatus.target_format || 'docx'}
        />
      </section>

      {/* Download */}
      <section>
        <DownloadCard
          fileId={taskStatus.file_id || ''}
          fileName={fileName}
          fileSize={fileSize}
          targetFormat={taskStatus.target_format || 'docx'}
          taskId={taskId}
        />
      </section>
    </div>
  );
}
