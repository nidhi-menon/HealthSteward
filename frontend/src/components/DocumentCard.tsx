import { Button } from './Button';
import type { Document } from '../types';

interface DocumentCardProps {
  document: Document;
  onParse: (id: string) => void;
  onDelete: (id: string) => void;
  isParsing?: boolean;
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  parsing: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentCard({ document: doc, onParse, onDelete, isParsing }: DocumentCardProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:border-emerald-300 transition-colors">
      <div className="flex justify-between items-start">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <svg className="h-8 w-8 text-red-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM14 3.5L18.5 8H14V3.5zM6 20V4h7v5h5v11H6z"/>
          </svg>
          <div className="min-w-0">
            <h4 className="font-medium text-gray-900 truncate">{doc.original_filename}</h4>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-sm text-gray-500">
              <span>{formatSize(doc.file_size_bytes)}</span>
              {doc.visit_date && <span>Visit: {doc.visit_date}</span>}
              {doc.provider_name && <span>{doc.provider_name}</span>}
              {doc.facility_name && <span>{doc.facility_name}</span>}
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[doc.parse_status] || 'bg-gray-100 text-gray-700'}`}>
                {doc.parse_status === 'parsing' ? 'Parsing...' : doc.parse_status}
              </span>
              {doc.parse_error && (
                <span className="text-xs text-red-600 truncate max-w-xs" title={doc.parse_error}>
                  {doc.parse_error}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-start gap-2 ml-4">
          {(doc.parse_status === 'pending' || doc.parse_status === 'completed') && (
            <Button
              size="sm"
              variant={doc.parse_status === 'completed' ? 'secondary' : 'primary'}
              onClick={() => onParse(doc.id)}
              disabled={isParsing}
            >
              {isParsing ? 'Parsing...' : doc.parse_status === 'completed' ? 'Review' : 'Parse'}
            </Button>
          )}
          {doc.parse_status === 'failed' && (
            <Button
              size="sm"
              onClick={() => onParse(doc.id)}
              disabled={isParsing}
            >
              Retry
            </Button>
          )}
          <button
            onClick={() => onDelete(doc.id)}
            className="text-gray-400 hover:text-red-600 transition-colors p-1"
            title="Delete document"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
