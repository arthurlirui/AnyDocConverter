'use client';

import Link from 'next/link';
import { FileText } from 'lucide-react';

export default function Header() {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-9 h-9 bg-primary-600 rounded-xl flex items-center justify-center group-hover:bg-primary-700 transition-colors">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900">PDF Platform</span>
          </Link>

          <nav className="flex items-center gap-4">
            <span className="text-sm text-gray-500 hidden sm:block">
              Online PDF Converter
            </span>
            <Link
              href="/"
              className="text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors"
            >
              Home
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}
