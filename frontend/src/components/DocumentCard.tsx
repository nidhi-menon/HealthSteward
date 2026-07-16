import { Button } from './Button';
import type { ScannedFile } from '../types';

interface DocumentCardProps {
  file: ScannedFile;
  onParse: (filename: string, documentId: string | null) => void;
  isParsing?: boolean;
}

const STATUS_STYLES: Record<string, string> = {
  new: 'bg-purple-100 text-purple-700',
  pending: 'bg-yellow-100 text-yellow-700',
  parsing: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

const STATUS_LABELS: Record<string, string> = {
  new: 'New',
  pending: 'pending',
  parsing: 'Parsing...',
  completed: 'completed',
  failed: 'failed',
};

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function DocumentCard({ file, onParse, isParsing }: DocumentCardProps) {
  const showActionButton = file.status !== 'parsing';

  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:border-brand-teal-bright/40 transition-colors">
      <div className="flex justify-between items-start">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <svg className="h-8 w-8 text-red-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM14 3.5L18.5 8H14V3.5zM6 20V4h7v5h5v11H6z"/>
          </svg>
          <div className="min-w-0">
            <h4 className="font-medium text-gray-900 truncate">{file.filename}</h4>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-sm text-gray-500">
              <span>{formatSize(file.file_size_bytes)}</span>
              <span>Modified: {formatDate(file.modified_date)}</span>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[file.status] || 'bg-gray-100 text-gray-700'}`}>
                {STATUS_LABELS[file.status] || file.status}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-start gap-2 ml-4">
          {showActionButton && (
            <Button
              size="sm"
              variant={file.status === 'completed' ? 'secondary' : 'primary'}
              onClick={() => onParse(file.filename, file.document_id)}
              disabled={isParsing}
            >
              {isParsing
                ? 'Parsing...'
                : file.status === 'completed'
                  ? 'Review'
                  : file.status === 'failed'
                    ? 'Retry'
                    : 'Parse'}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
