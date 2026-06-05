'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTaskStore } from '@/stores/taskStore';
import ProgressDisplay from '@/components/progress/ProgressDisplay';

export default function ConvertTaskPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.taskId as string;
  const { taskStatus, pollTask, stopPolling, phase } = useTaskStore();

  // Start polling on mount
  useEffect(() => {
    if (taskId) {
      pollTask(taskId);
      const interval = setInterval(() => {
        pollTask(taskId);
      }, 1500);
      return () => clearInterval(interval);
    }
  }, [taskId, pollTask]);

  // Redirect to result if already completed
  useEffect(() => {
    if (phase === 'completed' && taskStatus?.file_id) {
      const timer = setTimeout(() => {
        router.push(`/convert/${taskId}/result`);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [phase, taskStatus, taskId, router]);

  // Cleanup
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-12">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Converting your file
        </h1>
        <p className="text-gray-500 text-sm">
          Please wait while we process your document
        </p>
      </div>

      <ProgressDisplay taskId={taskId} />
    </div>
  );
}
