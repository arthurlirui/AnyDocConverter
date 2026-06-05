'use client';

import { useTaskStore } from '@/stores/taskStore';

const COLOR_MODES = ['rgb', 'cmyk', 'grayscale'];

export default function ImageQualityOptions() {
  const { params, updateParams } = useTaskStore();

  const image = params.image || { dpi: 300, compression: 'jpeg', quality: 95, color_space: 'rgb' };

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-gray-700">Image Quality</h4>

      <div>
        <div className="flex justify-between mb-1">
          <label className="text-xs text-gray-500">Quality</label>
          <span className="text-xs text-gray-500 font-medium">
            {image.quality}%
          </span>
        </div>
        <input
          type="range"
          min={10}
          max={100}
          step={5}
          value={image.quality}
          onChange={(e) =>
            updateParams({ image: { ...image, quality: parseInt(e.target.value) } })
          }
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
        />
        <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
          <span>Smaller file</span>
          <span>Better quality</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">DPI</label>
          <select
            value={image.dpi}
            onChange={(e) =>
              updateParams({ image: { ...image, dpi: parseInt(e.target.value) } })
            }
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value={72}>72 (Screen)</option>
            <option value={150}>150 (Draft)</option>
            <option value={300}>300 (Standard)</option>
            <option value={600}>600 (High)</option>
          </select>
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">Color Mode</label>
          <select
            value={image.color_space}
            onChange={(e) =>
              updateParams({ image: { ...image, color_space: e.target.value } })
            }
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            {COLOR_MODES.map((mode) => (
              <option key={mode} value={mode}>
                {mode.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
