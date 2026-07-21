'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTaskStore } from '@/stores/taskStore';
import PreviewCompare from '@/components/preview/PreviewCompare';
import DownloadCard from '@/components/result/DownloadCard';
import { Loader2, AlertCircle } from 'lucide-react';

export default function ConvertResultPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.taskId as string;
  const {
    taskStatus,
    pollTask,
    startPolling,
    stopPolling,
    phase,
    uploadedFileName,
    file,
    pollInterval,
    taskId: storeTaskId,
  } = useTaskStore();
  const fileName = taskStatus?.file_name || uploadedFileName || file?.name || 'file.pdf';
  const fileSize = taskStatus?.file_size || file?.size || 0;

  // If the user lands here directly (refresh / direct URL) the store is fresh:
  // taskStatus is null and no polling is running. Do a single poll to hydrate
  // the store; if the task is not terminal, start the store-managed polling
  // interval. We deliberately do NOT create a local setInterval here — that
  // was the source of a bug where polling ran forever after completion
  // because the local interval was never registered with the store and
  // stopPolling() could not clear it.
  useEffect(() => {
    const isTerminal =
      taskStatus?.status === 'completed' || taskStatus?.status === 'failed';
    if (isTerminal) return;
    // If the store is already polling this task (e.g. we came from the
    // convert page), let it continue. Otherwise hydrate once and, if the
    // task is still running, start polling.
    if (pollInterval && storeTaskId === taskId) return;
    void pollTask(taskId).then(() => {
      const ts = useTaskStore.getState().taskStatus;
      const stillRunning =
        ts && ts.status !== 'completed' && ts.status !== 'failed';
      if (stillRunning) {
        startPolling(taskId);
      }
    });
    // Run once on mount / when taskId changes. Including taskStatus would
    // re-trigger the effect on every poll and cause fetch storms.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  // When navigating away from this page, stop the store-managed polling so
  // we don't keep fetching a task the user is no longer viewing.
  useEffect(() => {
    return () => {
      // Only stop polling if this page owns the current task. If the user
      // started a new conversion in another tab we don't want to kill it.
      if (storeTaskId === taskId) {
        stopPolling();
      }
    };
  }, [stopPolling, storeTaskId, taskId]);

  // Failed-task UX: show an inline error card with a retry action. We do NOT
  // auto-redirect to the convert page (the previous behavior) because that
  // page spins forever on a failed task and gives the user no feedback.
  if (taskStatus && taskStatus.status === 'failed') {
    return (
      <div className="max-w-lg mx-auto px-4 sm:px-6 py-16 text-center">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <AlertCircle className="w-8 h-8 text-red-600" />
        </div>
        <h2 className="text-xl font-bold text-gray-800">Conversion Failed</h2>
        <p className="text-sm text-gray-500 mt-2 mb-6 break-words">
          {taskStatus.error_message || 'An unexpected error occurred during conversion.'}
        </p>
        <button
          onClick={() => router.push('/')}
          className="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white font-semibold py-2.5 px-6 rounded-xl transition-colors"
        >
          Start Over
        </button>
      </div>
    );
  }

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
          fileId={taskId}
          fileName={fileName}
          fileSize={fileSize}
          targetFormat={taskStatus.target_format || 'docx'}
          taskId={taskId}
        />
      </section>
    </div>
  );
}
