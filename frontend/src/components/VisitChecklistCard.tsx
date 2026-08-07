import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { appointments } from '../api/client';
import { Card, CardHeader, CardContent } from './Card';

interface Props {
  profileId: string;
  appointmentId: string;
}

const CATEGORY_ORDER = ['paperwork', 'records', 'medications', 'questions', 'logistics'];

const CATEGORY_LABELS: Record<string, string> = {
  paperwork: 'Paperwork',
  records: 'Records to bring',
  medications: 'Medications & allergies',
  questions: 'For the conversation',
  logistics: 'Before you go',
};

/**
 * Tick-off state lives in localStorage rather than the database (issue #110).
 * It is a scratchpad for one visit, not health data worth a table and a
 * migration — and it resets harmlessly if the browser is cleared.
 */
function storageKey(appointmentId: string): string {
  return `healthsteward.checklist.${appointmentId}`;
}

function loadChecked(appointmentId: string): Set<string> {
  try {
    const raw = window.localStorage.getItem(storageKey(appointmentId));
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    // Private-browsing modes and quota errors shouldn't take the card down.
    return new Set();
  }
}

function saveChecked(appointmentId: string, checked: Set<string>): void {
  try {
    window.localStorage.setItem(storageKey(appointmentId), JSON.stringify([...checked]));
  } catch {
    // Ticking a box is not worth an error state; it just won't persist.
  }
}

export function VisitChecklistCard({ profileId, appointmentId }: Props) {
  const { data: checklist, isLoading } = useQuery({
    queryKey: ['visitChecklist', profileId, appointmentId],
    queryFn: () => appointments.checklist(profileId, appointmentId),
  });

  const [checked, setChecked] = useState<Set<string>>(() => loadChecked(appointmentId));

  const toggle = (id: string) => {
    setChecked(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      saveChecked(appointmentId, next);
      return next;
    });
  };

  if (isLoading) return null;
  if (!checklist || checklist.items.length === 0) return null;

  const categories = CATEGORY_ORDER.filter(category =>
    checklist.items.some(item => item.category === category),
  );
  const remaining = checklist.items.filter(item => !checked.has(item.id)).length;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900">What to bring</h3>
            <p className="text-sm text-gray-500 mt-0.5">
              Based on this visit and what's already in your profile.
            </p>
          </div>
          <span className="text-sm text-gray-500 flex-shrink-0">
            {remaining === 0
              ? 'All set'
              : `${remaining} of ${checklist.items.length} left`}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {categories.map(category => (
          <div key={category}>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              {CATEGORY_LABELS[category] ?? category}
            </h4>
            <ul className="mt-1.5 space-y-1.5">
              {checklist.items
                .filter(item => item.category === category)
                .map(item => (
                  <li key={item.id}>
                    <label className="flex items-start gap-2.5 cursor-pointer group">
                      <input
                        type="checkbox"
                        checked={checked.has(item.id)}
                        onChange={() => toggle(item.id)}
                        className="mt-0.5 h-4 w-4 flex-shrink-0 rounded border-gray-300 text-brand-teal-bright focus:ring-brand-teal-bright"
                      />
                      <span className="min-w-0">
                        <span
                          className={`block text-sm ${
                            checked.has(item.id)
                              ? 'text-gray-400 line-through'
                              : 'text-gray-800'
                          }`}
                        >
                          {item.label}
                        </span>
                        <span className="block text-xs text-gray-500">{item.why}</span>
                      </span>
                    </label>
                  </li>
                ))}
            </ul>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
