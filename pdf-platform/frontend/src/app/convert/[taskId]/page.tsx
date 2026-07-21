'use client';

import { useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTaskStore } from '@/stores/taskStore';
import ProgressDisplay from '@/components/progress/ProgressDisplay';

export default function ConvertTaskPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.taskId as string;
  const { taskStatus, pollTask, stopPolling, phase } = useTaskStore();
  const redirectDispatched = useRef(false);

  // Start polling on mount.
  //
  // 注意：taskStore.createAndStartTask 内部已经启动了一个 setInterval 轮询
  // 并写入 store.pollInterval。这里若再起一个本地 setInterval 会导致同一任务
  // 被并发轮询两次（双倍请求）。因此本页面只在 store 尚未轮询时补一次首拉，
  // 后续轮询完全交给 store 管理；卸载时调用 stopPolling 统一清理。
  useEffect(() => {
    if (!taskId) return;

    let cancelled = false;

    const doPoll = async () => {
      if (cancelled) return;
      await pollTask(taskId);
    };

    // 首次拉取（用于刷新页面 / 直接访问 URL 的场景）
    doPoll();

    // 终态判定交给 store 内部的 pollTask，触发后 stopPolling 自动停止。
    const { pollInterval } = useTaskStore.getState();
    if (!pollInterval) {
      const interval = setInterval(doPoll, 1500);
      // 注册到 store，使 stopPolling 能统一清理，避免重复轮询
      useTaskStore.setState({ pollInterval: interval });
    }

    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [taskId, pollTask, stopPolling]);

  // Redirect to result if already completed
  useEffect(() => {
    if (phase === 'completed' && taskStatus?.file_id && !redirectDispatched.current) {
      redirectDispatched.current = true;
      router.push(`/convert/${taskId}/result`);
    }
  }, [phase, taskStatus?.file_id, taskId, router]);

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

      <ProgressDisplay />
    </div>
  );
}
