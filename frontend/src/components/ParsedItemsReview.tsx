import { useState, useCallback } from 'react';
import { Button } from './Button';
import { Card, CardHeader, CardContent } from './Card';
import type {
  ParsedItemsResponse,
  ApplyItemsRequest,
  ParsedDiagnosis,
  ParsedMedicationChange,
  ParsedVitals,
  ParsedLabOrder,
  ParsedReferral,
  ParsedFollowUp,
} from '../types';

interface ParsedItemsReviewProps {
  data: ParsedItemsResponse;
  onApply: (items: ApplyItemsRequest) => void;
  onBack: () => void;
  isApplying: boolean;
}

const ACTION_STYLES: Record<string, string> = {
  start: 'bg-green-100 text-green-700',
  stop: 'bg-red-100 text-red-700',
  changed: 'bg-yellow-100 text-yellow-700',
};

export function ParsedItemsReview({ data, onApply, onBack, isApplying }: ParsedItemsReviewProps) {
  const [selectedDiagnoses, setSelectedDiagnoses] = useState<Set<number>>(
    new Set(data.diagnoses.map((_, i) => i))
  );
  const [selectedMedStarts, setSelectedMedStarts] = useState<Set<number>>(
    new Set(data.medication_changes.filter(m => m.action === 'start').map((_, i) => i))
  );
  const [selectedMedStops, setSelectedMedStops] = useState<Set<number>>(
    new Set(data.medication_changes.filter(m => m.action === 'stop').map((_, i) => i))
  );
  const [selectedVitals, setSelectedVitals] = useState(true);
  const [selectedLabOrders, setSelectedLabOrders] = useState<Set<number>>(
    new Set(data.lab_orders.map((_, i) => i))
  );
  const [selectedReferrals, setSelectedReferrals] = useState<Set<number>>(
    new Set(data.referrals.map((_, i) => i))
  );
  const [selectedFollowUps, setSelectedFollowUps] = useState<Set<number>>(
    new Set(data.follow_up_recommended.map((_, i) => i))
  );

  const toggleSet = useCallback((set: Set<number>, index: number, setter: (s: Set<number>) => void) => {
    const next = new Set(set);
    if (next.has(index)) {
      next.delete(index);
    } else {
      next.add(index);
    }
    setter(next);
  }, []);

  const toggleAll = useCallback((items: unknown[], set: Set<number>, setter: (s: Set<number>) => void) => {
    if (set.size === items.length) {
      setter(new Set());
    } else {
      setter(new Set(items.map((_, i) => i)));
    }
  }, []);

  const medStarts = data.medication_changes.filter(m => m.action === 'start');
  const medStops = data.medication_changes.filter(m => m.action === 'stop');
  const medChanged = data.medication_changes.filter(m => m.action === 'changed');

  const hasVitals = data.vitals && (
    data.vitals.weight || data.vitals.bmi || data.vitals.blood_pressure ||
    data.vitals.heart_rate || data.vitals.temperature
  );

  const handleApply = () => {
    const items: ApplyItemsRequest = {
      diagnoses: data.diagnoses.filter((_, i) => selectedDiagnoses.has(i)),
      medication_starts: medStarts.filter((_, i) => selectedMedStarts.has(i)),
      medication_stops: medStops.filter((_, i) => selectedMedStops.has(i)),
      vitals: selectedVitals && hasVitals ? data.vitals : null,
      lab_orders: data.lab_orders.filter((_, i) => selectedLabOrders.has(i)),
      referrals: data.referrals.filter((_, i) => selectedReferrals.has(i)),
      follow_ups: data.follow_up_recommended.filter((_, i) => selectedFollowUps.has(i)),
    };
    onApply(items);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Review Extracted Items</h3>
          <p className="text-sm text-gray-500 mt-1">
            {data.patient.name && `Patient: ${data.patient.name}`}
            {data.patient.visit_date && ` | Visit: ${data.patient.visit_date}`}
            {data.provider.name && ` | Provider: ${data.provider.name}`}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={onBack}>Back to List</Button>
      </div>

      {/* Vitals */}
      {hasVitals && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-gray-900">Vitals</h4>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selectedVitals}
                  onChange={() => setSelectedVitals(!selectedVitals)}
                  className="h-4 w-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                />
                Include
              </label>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
              {data.vitals.weight && <VitalItem label="Weight" value={data.vitals.weight} />}
              {data.vitals.bmi && <VitalItem label="BMI" value={String(data.vitals.bmi)} />}
              {data.vitals.blood_pressure && <VitalItem label="Blood Pressure" value={data.vitals.blood_pressure} />}
              {data.vitals.heart_rate && <VitalItem label="Heart Rate" value={data.vitals.heart_rate} />}
              {data.vitals.temperature && <VitalItem label="Temperature" value={data.vitals.temperature} />}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Diagnoses */}
      {data.diagnoses.length > 0 && (
        <CheckboxSection
          title="Diagnoses"
          items={data.diagnoses}
          selected={selectedDiagnoses}
          onToggle={(i) => toggleSet(selectedDiagnoses, i, setSelectedDiagnoses)}
          onToggleAll={() => toggleAll(data.diagnoses, selectedDiagnoses, setSelectedDiagnoses)}
          renderItem={(dx: ParsedDiagnosis) => (
            <div className="flex items-center gap-2">
              <span>{dx.condition}</span>
              {dx.icd_10 && (
                <span className="px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                  {dx.icd_10}
                </span>
              )}
            </div>
          )}
        />
      )}

      {/* Medication Starts */}
      {medStarts.length > 0 && (
        <CheckboxSection
          title="Medications — START"
          items={medStarts}
          selected={selectedMedStarts}
          onToggle={(i) => toggleSet(selectedMedStarts, i, setSelectedMedStarts)}
          onToggleAll={() => toggleAll(medStarts, selectedMedStarts, setSelectedMedStarts)}
          renderItem={(med: ParsedMedicationChange) => (
            <MedItem med={med} />
          )}
        />
      )}

      {/* Medication Stops */}
      {medStops.length > 0 && (
        <CheckboxSection
          title="Medications — STOP"
          items={medStops}
          selected={selectedMedStops}
          onToggle={(i) => toggleSet(selectedMedStops, i, setSelectedMedStops)}
          onToggleAll={() => toggleAll(medStops, selectedMedStops, setSelectedMedStops)}
          renderItem={(med: ParsedMedicationChange) => (
            <MedItem med={med} />
          )}
        />
      )}

      {/* Medication Changes (read-only) */}
      {medChanged.length > 0 && (
        <Card>
          <CardHeader>
            <h4 className="font-semibold text-gray-900">Medications — CHANGED (info only)</h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {medChanged.map((med, i) => (
                <div key={i} className="text-sm text-gray-700">
                  <MedItem med={med} />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Lab Orders */}
      {data.lab_orders.length > 0 && (
        <CheckboxSection
          title="Lab Orders"
          items={data.lab_orders}
          selected={selectedLabOrders}
          onToggle={(i) => toggleSet(selectedLabOrders, i, setSelectedLabOrders)}
          onToggleAll={() => toggleAll(data.lab_orders, selectedLabOrders, setSelectedLabOrders)}
          renderItem={(lab: ParsedLabOrder) => (
            <div className="flex items-center gap-2">
              <span>{lab.test}</span>
              {lab.ordered_date && <span className="text-gray-400 text-xs">({lab.ordered_date})</span>}
            </div>
          )}
        />
      )}

      {/* Referrals */}
      {data.referrals.length > 0 && (
        <CheckboxSection
          title="Referrals"
          items={data.referrals}
          selected={selectedReferrals}
          onToggle={(i) => toggleSet(selectedReferrals, i, setSelectedReferrals)}
          onToggleAll={() => toggleAll(data.referrals, selectedReferrals, setSelectedReferrals)}
          renderItem={(ref: ParsedReferral) => (
            <div>
              <span className="font-medium">{ref.specialty}</span>
              {ref.provider && <span className="text-gray-500"> — {ref.provider}</span>}
              {ref.reason && <span className="text-gray-500 text-xs ml-2">({ref.reason})</span>}
            </div>
          )}
        />
      )}

      {/* Follow-ups */}
      {data.follow_up_recommended.length > 0 && (
        <CheckboxSection
          title="Follow-up Recommendations"
          items={data.follow_up_recommended}
          selected={selectedFollowUps}
          onToggle={(i) => toggleSet(selectedFollowUps, i, setSelectedFollowUps)}
          onToggleAll={() => toggleAll(data.follow_up_recommended, selectedFollowUps, setSelectedFollowUps)}
          renderItem={(fu: ParsedFollowUp) => (
            <div>
              <span>{fu.description}</span>
              {fu.timeframe && <span className="text-gray-500 text-xs ml-2">({fu.timeframe})</span>}
              {fu.target_date && <span className="text-gray-400 text-xs ml-1">target: {fu.target_date}</span>}
            </div>
          )}
        />
      )}

      {/* Upcoming Appointments (read-only) */}
      {data.upcoming_appointments.length > 0 && (
        <Card>
          <CardHeader>
            <h4 className="font-semibold text-gray-900">Upcoming Appointments (info only)</h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.upcoming_appointments.map((appt, i) => (
                <div key={i} className="text-sm text-gray-700">
                  <span className="font-medium">{appt.description}</span>
                  {appt.date && <span className="ml-2">{appt.date}</span>}
                  {appt.time && <span className="ml-1">{appt.time}</span>}
                  {appt.location && <span className="text-gray-500 ml-2">{appt.location}</span>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Notes (read-only) */}
      {data.notes.length > 0 && (
        <Card>
          <CardHeader>
            <h4 className="font-semibold text-gray-900">Notes & Instructions (info only)</h4>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {data.notes.map((note, i) => (
                <li key={i} className="text-sm text-gray-700 pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-gray-400">
                  {note}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Action buttons */}
      <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
        <Button variant="secondary" onClick={onBack}>Cancel</Button>
        <Button onClick={handleApply} disabled={isApplying}>
          {isApplying ? 'Applying...' : 'Confirm & Update Profile'}
        </Button>
      </div>
    </div>
  );
}

function VitalItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-gray-500">{label}</span>
      <p className="font-medium text-gray-900">{value}</p>
    </div>
  );
}

function MedItem({ med }: { med: ParsedMedicationChange }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="font-medium">{med.name}</span>
      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${ACTION_STYLES[med.action] || ''}`}>
        {med.action.toUpperCase()}
      </span>
      {med.strength && <span className="text-gray-500 text-xs">{med.strength}</span>}
      {med.instructions && <span className="text-gray-400 text-xs truncate max-w-sm">{med.instructions}</span>}
    </div>
  );
}

interface CheckboxSectionProps<T> {
  title: string;
  items: T[];
  selected: Set<number>;
  onToggle: (index: number) => void;
  onToggleAll: () => void;
  renderItem: (item: T) => React.ReactNode;
}

function CheckboxSection<T>({ title, items, selected, onToggle, onToggleAll, renderItem }: CheckboxSectionProps<T>) {
  const allSelected = selected.size === items.length;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h4 className="font-semibold text-gray-900">{title}</h4>
          <button
            onClick={onToggleAll}
            className="text-xs text-emerald-600 hover:text-emerald-700"
          >
            {allSelected ? 'Deselect all' : 'Select all'}
          </button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {items.map((item, i) => (
            <label key={i} className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={selected.has(i)}
                onChange={() => onToggle(i)}
                className="h-4 w-4 mt-0.5 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
              />
              <div className="text-sm text-gray-700 group-hover:text-gray-900">
                {renderItem(item)}
              </div>
            </label>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
