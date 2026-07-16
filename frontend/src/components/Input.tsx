import { useState, useEffect } from 'react';
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
          focus:border-brand-teal-bright focus:ring-1 focus:ring-brand-teal-bright
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
          focus:border-brand-teal-bright focus:ring-1 focus:ring-brand-teal-bright
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
          focus:border-brand-teal-bright focus:ring-1 focus:ring-brand-teal-bright
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

interface MonthYearInputProps {
  label?: string;
  error?: string;
  value: string | null;  // Format: "YYYY-MM-DD" or null
  onChange: (value: string | null) => void;
  minYear?: number;
  maxYear?: number;
}

export function MonthYearInput({
  label,
  error,
  value,
  onChange,
  minYear = 1950,
  maxYear = new Date().getFullYear()
}: MonthYearInputProps) {
  // Use local state to track partial selections
  const [localMonth, setLocalMonth] = useState<string | null>(
    value ? value.substring(5, 7) : null
  );
  const [localYear, setLocalYear] = useState<number | null>(
    value ? parseInt(value.substring(0, 4)) : null
  );

  // Sync local state when value prop changes externally
  useEffect(() => {
    if (value) {
      setLocalMonth(value.substring(5, 7));
      setLocalYear(parseInt(value.substring(0, 4)));
    } else {
      setLocalMonth(null);
      setLocalYear(null);
    }
  }, [value]);

  const months = [
    { value: '01', label: 'January' },
    { value: '02', label: 'February' },
    { value: '03', label: 'March' },
    { value: '04', label: 'April' },
    { value: '05', label: 'May' },
    { value: '06', label: 'June' },
    { value: '07', label: 'July' },
    { value: '08', label: 'August' },
    { value: '09', label: 'September' },
    { value: '10', label: 'October' },
    { value: '11', label: 'November' },
    { value: '12', label: 'December' },
  ];

  const years = Array.from(
    { length: maxYear - minYear + 1 },
    (_, i) => maxYear - i
  );

  const updateValue = (month: string | null, year: number | null) => {
    if (month && year) {
      onChange(`${year}-${month}-01`);
    }
  };

  const handleMonthChange = (month: string | null) => {
    setLocalMonth(month);
    updateValue(month, localYear);
  };

  const handleYearChange = (year: number | null) => {
    setLocalYear(year);
    updateValue(localMonth, year);
  };

  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <div className="flex gap-2">
        <select
          className={`
            flex-1 rounded-lg border border-gray-300 px-3 py-2
            text-gray-900
            focus:border-brand-teal-bright focus:ring-1 focus:ring-brand-teal-bright
            ${error ? 'border-red-500' : ''}
          `}
          value={localMonth || ''}
          onChange={(e) => handleMonthChange(e.target.value || null)}
        >
          <option value="">Month</option>
          {months.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
        <select
          className={`
            w-28 rounded-lg border border-gray-300 px-3 py-2
            text-gray-900
            focus:border-brand-teal-bright focus:ring-1 focus:ring-brand-teal-bright
            ${error ? 'border-red-500' : ''}
          `}
          value={localYear || ''}
          onChange={(e) => handleYearChange(e.target.value ? parseInt(e.target.value) : null)}
        >
          <option value="">Year</option>
          {years.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}

interface DatePickerProps {
  label?: string;
  error?: string;
  value: string | null;  // Format: "YYYY-MM-DD" or null
  onChange: (value: string | null) => void;
  minYear?: number;
  maxYear?: number;
}

export function DatePicker({
  label,
  error,
  value,
  onChange,
  minYear = 1920,
  maxYear = new Date().getFullYear()
}: DatePickerProps) {
  // Use local state to track partial selections
  const [localMonth, setLocalMonth] = useState<number | null>(
    value ? parseInt(value.substring(5, 7)) : null
  );
  const [localDay, setLocalDay] = useState<number | null>(
    value ? parseInt(value.substring(8, 10)) : null
  );
  const [localYear, setLocalYear] = useState<number | null>(
    value ? parseInt(value.substring(0, 4)) : null
  );

  // Sync local state when value prop changes externally
  useEffect(() => {
    if (value) {
      setLocalYear(parseInt(value.substring(0, 4)));
      setLocalMonth(parseInt(value.substring(5, 7)));
      setLocalDay(parseInt(value.substring(8, 10)));
    } else {
      setLocalYear(null);
      setLocalMonth(null);
      setLocalDay(null);
    }
  }, [value]);

  const months = [
    { value: 1, label: 'January' },
    { value: 2, label: 'February' },
    { value: 3, label: 'March' },
    { value: 4, label: 'April' },
    { value: 5, label: 'May' },
    { value: 6, label: 'June' },
    { value: 7, label: 'July' },
    { value: 8, label: 'August' },
    { value: 9, label: 'September' },
    { value: 10, label: 'October' },
    { value: 11, label: 'November' },
    { value: 12, label: 'December' },
  ];

  const years = Array.from(
    { length: maxYear - minYear + 1 },
    (_, i) => maxYear - i
  );

  // Calculate days in month
  const daysInMonth = localMonth && localYear
    ? new Date(localYear, localMonth, 0).getDate()
    : 31;
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);

  const updateValue = (day: number | null, month: number | null, year: number | null) => {
    if (day && month && year) {
      const mm = month.toString().padStart(2, '0');
      const dd = day.toString().padStart(2, '0');
      onChange(`${year}-${mm}-${dd}`);
    }
  };

  const handleMonthChange = (month: number | null) => {
    setLocalMonth(month);
    updateValue(localDay, month, localYear);
  };

  const handleDayChange = (day: number | null) => {
    setLocalDay(day);
    updateValue(day, localMonth, localYear);
  };

  const handleYearChange = (year: number | null) => {
    setLocalYear(year);
    updateValue(localDay, localMonth, year);
  };

  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <div className="flex gap-2">
        <select
          className={`
            flex-1 rounded-lg border border-gray-300 px-3 py-2
            text-gray-900
            focus:border-brand-teal-bright focus:ring-1 focus:ring-brand-teal-bright
            ${error ? 'border-red-500' : ''}
          `}
          value={localMonth || ''}
          onChange={(e) => handleMonthChange(e.target.value ? parseInt(e.target.value) : null)}
        >
          <option value="">Month</option>
          {months.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
        <select
          className={`
            w-20 rounded-lg border border-gray-300 px-3 py-2
            text-gray-900
            focus:border-brand-teal-bright focus:ring-1 focus:ring-brand-teal-bright
            ${error ? 'border-red-500' : ''}
          `}
          value={localDay || ''}
          onChange={(e) => handleDayChange(e.target.value ? parseInt(e.target.value) : null)}
        >
          <option value="">Day</option>
          {days.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <select
          className={`
            w-24 rounded-lg border border-gray-300 px-3 py-2
            text-gray-900
            focus:border-brand-teal-bright focus:ring-1 focus:ring-brand-teal-bright
            ${error ? 'border-red-500' : ''}
          `}
          value={localYear || ''}
          onChange={(e) => handleYearChange(e.target.value ? parseInt(e.target.value) : null)}
        >
          <option value="">Year</option>
          {years.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
