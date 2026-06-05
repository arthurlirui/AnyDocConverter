import { FileText, Shield, Zap, Globe } from 'lucide-react';

const features = [
  {
    icon: Zap,
    title: 'Fast Conversion',
    description: 'Lightning-fast processing powered by efficient algorithms',
  },
  {
    icon: Shield,
    title: 'Secure & Private',
    description: 'Files are encrypted and automatically deleted after processing',
  },
  {
    icon: Globe,
    title: 'Multiple Formats',
    description: 'Convert to Word, Excel, PPT, Images, HTML, and more',
  },
  {
    icon: FileText,
    title: 'High Quality',
    description: 'Preserves fonts, layout, and formatting with precision',
  },
];

export default function Footer() {
  return (
    <footer className="bg-white border-t border-gray-200 mt-16">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-8">
          {features.map((feature) => (
            <div key={feature.title} className="text-center">
              <feature.icon className="w-6 h-6 text-primary-500 mx-auto mb-2" />
              <h4 className="text-sm font-semibold text-gray-700">
                {feature.title}
              </h4>
              <p className="text-xs text-gray-400 mt-1">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
        <div className="border-t border-gray-100 pt-6 text-center">
          <p className="text-xs text-gray-400">
            &copy; {new Date().getFullYear()} PDF Platform. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
