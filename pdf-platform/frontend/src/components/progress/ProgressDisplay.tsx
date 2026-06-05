'use client';

import { useEffect, useState } from 'react';
import { useTaskStore } from '@/stores/taskStore';
import { useRouter } from 'next/navigation';
import { Loader2, CheckCircle2, XCircle, FileText } from 'lucide-react';
import clsx from 'clsx';

const PHASE_STEPS = [
  { key: 'uploading', label: 'Upload', icon: FileText },
  { key: 'preparing', label: 'Prepare', icon: Loader2 },
  { key: 'processing', label: 'Process', icon: Loader2 },
  { key: 'finalizing', label: 'Finalize', icon: Loader2 },
  { key: 'completed', label: 'Done', icon: CheckCircle2 },
] as const;

interface ProgressDisplayProps {
  taskId: string;
}

export default function ProgressDisplay({ taskId }: ProgressDisplayProps) {
  const { phase, progress, phaseMessage, taskStatus } = useTaskStore();
  const router = useRouter();

  // Auto-redirect to result on completion
  useEffect(() => {
    if (phase === 'completed' && taskStatus?.file_id) {
      const timer = setTimeout(() => {
        router.push(`/convert/${taskId}/result`);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [phase, taskStatus, taskId, router]);

  const currentStepIndex = PHASE_STEPS.findIndex((s) => s.key === phase);

  return (
    <div className="max-w-lg mx-auto space-y-8">
      {/* Phase indicator */}
      <div className="flex items-center justify-between">
        {PHASE_STEPS.map((step, i) => {
          const isActive = i === currentStepIndex;
          const isCompleted = i < currentStepIndex;
          const isFailed = phase === 'failed' && i === currentStepIndex;

          return (
            <div key={step.key} className="flex flex-col items-center gap-1.5">
              <div
                className={clsx(
                  'w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300',
                  isCompleted && 'bg-green-100 text-green-600',
                  isActive &&
                    !isFailed &&
                    'bg-primary-100 text-primary-600 ring-4 ring-primary-200',
                  isFailed && 'bg-red-100 text-red-600 ring-4 ring-red-200',
                  !isActive && !isCompleted && !isFailed && 'bg-gray-100 text-gray-400'
                )}
              >
                {isCompleted ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : isFailed ? (
                  <XCircle className="w-5 h-5" />
                ) : (
                  <step.icon
                    className={clsx(
                      'w-5 h-5',
                      isActive && 'animate-spin'
                    )}
                  />
                )}
              </div>
              <span
                className={clsx(
                  'text-xs font-medium',
                  isCompleted && 'text-green-600',
                  isActive && !isFailed && 'text-primary-600',
                  isFailed && 'text-red-600',
                  !isActive && !isCompleted && !isFailed && 'text-gray-400'
                )}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">{phaseMessage}</span>
          <span className="font-semibold text-primary-600">{progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
          <div
            className={clsx(
              'h-full rounded-full transition-all duration-500 ease-out',
              phase === 'failed' ? 'bg-red-500' : 'bg-primary-600'
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Error */}
      {phase === 'failed' && taskStatus?.error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
          <XCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
          <p className="text-red-700 font-medium">Conversion Failed</p>
          <p className="text-sm text-red-500 mt-1">{taskStatus.error}</p>
        </div>
      )}

      {/* Success message */}
      {phase === 'completed' && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-center animate-pulse-slow">
          <CheckCircle2 className="w-8 h-8 text-green-500 mx-auto mb-2" />
          <p className="text-green-700 font-medium">Conversion Complete!</p>
          <p className="text-sm text-green-500 mt-1">
            Redirecting to download...
          </p>
        </div>
      )}
    </div>
  );
}
