import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className = '', ...props }: InputProps) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <input
        className={`
          block w-full rounded-lg border border-gray-300 px-3 py-2
          text-gray-900 placeholder-gray-400
          focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500
          disabled:bg-gray-50 disabled:text-gray-500
          ${error ? 'border-red-500' : ''}
          ${className}
        `}
        {...props}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}

export function Textarea({ label, error, className = '', ...props }: TextareaProps) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <textarea
        className={`
          block w-full rounded-lg border border-gray-300 px-3 py-2
          text-gray-900 placeholder-gray-400
          focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500
          disabled:bg-gray-50 disabled:text-gray-500
          ${error ? 'border-red-500' : ''}
          ${className}
        `}
        rows={3}
        {...props}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}

interface SelectProps extends InputHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: { value: string; label: string }[];
}

export function Select({ label, error, options, className = '', ...props }: SelectProps) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <select
        className={`
          block w-full rounded-lg border border-gray-300 px-3 py-2
          text-gray-900
          focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500
          disabled:bg-gray-50 disabled:text-gray-500
          ${error ? 'border-red-500' : ''}
          ${className}
        `}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
