import { useState, useCallback } from 'react';
import { Button } from './Button';
import { Card, CardHeader, CardContent } from './Card';
import { Modal } from './Modal';
import { StalePlanError } from '../api/client';
import type {
  ParsedItemsResponse,
  ApplyItemsRequest,
  ApplyPlan,
  ApplyPlanEntry,
  ParsedDiagnosis,
  ParsedMedicationChange,
  ParsedVitals,
  ParsedLabOrder,
  ParsedReferral,
  ParsedFollowUp,
  ParsedAppointment,
} from '../types';

interface ParsedItemsReviewProps {
  data: ParsedItemsResponse;
  onApply: (items: ApplyItemsRequest) => void;
  // Asks the backend what the apply would actually change, so the confirm step
  // shows real per-field diffs instead of a list of incoming items (issue #46).
  onPreview: (items: ApplyItemsRequest) => Promise<ApplyPlan>;
  onBack: () => void;
  isApplying: boolean;
  applyError?: unknown;
}

const ENTITY_LABELS: Record<string, string> = {
  condition: 'Condition',
  medication: 'Medication',
  vitals: 'Vitals',
  lab_order: 'Lab order',
  referral: 'Referral',
  follow_up: 'Follow-up',
  appointment: 'Appointment',
  doctor: 'Doctor',
};

// ── Main Component ──

export function ParsedItemsReview({
  data, onApply, onPreview, onBack, isApplying, applyError,
}: ParsedItemsReviewProps) {
  // Editable copies of all items
  const [diagnoses, setDiagnoses] = useState<ParsedDiagnosis[]>(() => data.diagnoses.map(d => ({ ...d })));
  const [vitals, setVitals] = useState<ParsedVitals>(() => ({ ...data.vitals }));
  const [labOrders, setLabOrders] = useState<ParsedLabOrder[]>(() => data.lab_orders.map(l => ({ ...l })));
  const [referrals, setReferrals] = useState<ParsedReferral[]>(() => data.referrals.map(r => ({ ...r })));
  const [followUps, setFollowUps] = useState<ParsedFollowUp[]>(() => data.follow_up_recommended.map(f => ({ ...f })));
  const [appointments, setAppointments] = useState<ParsedAppointment[]>(() => data.upcoming_appointments.map(a => ({ ...a })));
  const [notes, setNotes] = useState<string[]>(() => [...data.notes]);

  const medStarts = data.medication_changes.filter(m => m.action === 'start');
  const medStops = data.medication_changes.filter(m => m.action === 'stop');
  const medChanged = data.medication_changes.filter(m => m.action === 'changed');

  const [editMedStarts, setEditMedStarts] = useState<ParsedMedicationChange[]>(() => medStarts.map(m => ({ ...m })));
  const [editMedStops, setEditMedStops] = useState<ParsedMedicationChange[]>(() => medStops.map(m => ({ ...m })));
  const [editMedUpdates, setEditMedUpdates] = useState<ParsedMedicationChange[]>(() => medChanged.map(m => ({ ...m })));

  // Track edits: "section-index-field" keys
  const [edits, setEdits] = useState<Set<string>>(new Set());

  // Confirmation modal, and the plan being confirmed
  const [showConfirm, setShowConfirm] = useState(false);
  const [plan, setPlan] = useState<ApplyPlan | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);

  // A refused apply hands back a freshly derived plan — show that instead of
  // the one the user reviewed, so they are confirming against current data.
  const stalePlan = applyError instanceof StalePlanError ? applyError.plan : null;
  const displayPlan = stalePlan ?? plan;

  const markEdit = useCallback((key: string) => {
    setEdits(prev => new Set(prev).add(key));
  }, []);

  const isEdited = useCallback((key: string) => edits.has(key), [edits]);

  const hasVitals = vitals && (
    vitals.weight || vitals.bmi || vitals.blood_pressure ||
    vitals.heart_rate || vitals.temperature
  );

  const removeItem = <T,>(list: T[], index: number, setter: (items: T[]) => void) => {
    setter(list.filter((_, i) => i !== index));
  };

  const buildApplyRequest = (): ApplyItemsRequest => ({
    diagnoses,
    medication_starts: editMedStarts,
    medication_stops: editMedStops,
    medication_updates: editMedUpdates,
    vitals: hasVitals ? vitals : null,
    lab_orders: labOrders,
    referrals,
    follow_ups: followUps,
    appointments,
  });

  const openConfirm = async () => {
    setShowConfirm(true);
    setPlan(null);
    setPlanError(null);
    setIsPreviewing(true);
    try {
      setPlan(await onPreview(buildApplyRequest()));
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : 'Could not work out what would change.');
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleConfirmApply = () => {
    if (!displayPlan) return;
    // Adopt the re-derived plan so a retry confirms what is on screen, not the
    // plan that was already refused once.
    if (stalePlan) setPlan(stalePlan);
    // The modal stays open: a successful apply unmounts this view, and a
    // refused one needs somewhere to show the re-derived plan.
    onApply({
      ...buildApplyRequest(),
      expected_plan_fingerprint: displayPlan.plan_fingerprint,
    });
  };

  const editCount = edits.size;

  // Count items for confirmation summary
  const itemCounts = {
    diagnoses: diagnoses.length,
    medStarts: editMedStarts.length,
    medStops: editMedStops.length,
    medUpdates: editMedUpdates.length,
    vitals: hasVitals ? 1 : 0,
    labOrders: labOrders.length,
    referrals: referrals.length,
    followUps: followUps.length,
    appointments: appointments.length,
  };
  const totalItems = Object.values(itemCounts).reduce((a, b) => a + b, 0);

  const planEntries = displayPlan?.entries ?? [];
  const updateEntries = planEntries.filter(e => e.action === 'update');
  const createEntries = planEntries.filter(e => e.action === 'create');
  const skipEntries = planEntries.filter(e => e.action === 'skip');

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
          <p className="text-xs text-gray-400 mt-1">
            Click any value to edit. Use <span className="font-mono">&times;</span> to remove items. All changes require confirmation before applying.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={onBack}>Back to List</Button>
      </div>

      {/* Vitals */}
      {hasVitals && (
        <Card>
          <CardHeader>
            <h4 className="font-semibold text-gray-900">Vitals</h4>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
              {data.vitals.weight != null && (
                <EditableVital
                  label="Weight"
                  value={vitals.weight || ''}
                  edited={isEdited('vitals-weight')}
                  onChange={(v) => { setVitals(prev => ({ ...prev, weight: v || null })); markEdit('vitals-weight'); }}
                />
              )}
              {data.vitals.bmi != null && (
                <EditableVital
                  label="BMI"
                  value={vitals.bmi != null ? String(vitals.bmi) : ''}
                  edited={isEdited('vitals-bmi')}
                  onChange={(v) => { setVitals(prev => ({ ...prev, bmi: v ? parseFloat(v) || null : null })); markEdit('vitals-bmi'); }}
                />
              )}
              {data.vitals.blood_pressure != null && (
                <EditableVital
                  label="Blood Pressure"
                  value={vitals.blood_pressure || ''}
                  edited={isEdited('vitals-bp')}
                  onChange={(v) => { setVitals(prev => ({ ...prev, blood_pressure: v || null })); markEdit('vitals-bp'); }}
                />
              )}
              {data.vitals.heart_rate != null && (
                <EditableVital
                  label="Heart Rate"
                  value={vitals.heart_rate || ''}
                  edited={isEdited('vitals-hr')}
                  onChange={(v) => { setVitals(prev => ({ ...prev, heart_rate: v || null })); markEdit('vitals-hr'); }}
                />
              )}
              {data.vitals.temperature != null && (
                <EditableVital
                  label="Temperature"
                  value={vitals.temperature || ''}
                  edited={isEdited('vitals-temp')}
                  onChange={(v) => { setVitals(prev => ({ ...prev, temperature: v || null })); markEdit('vitals-temp'); }}
                />
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Diagnoses */}
      {diagnoses.length > 0 && (
        <EditableSection title="Diagnoses">
          {diagnoses.map((dx, i) => (
            <RemovableRow key={i} onRemove={() => removeItem(diagnoses, i, setDiagnoses)}>
              <EditableField
                value={dx.condition}
                edited={isEdited(`dx-${i}-condition`)}
                onChange={(v) => {
                  const next = [...diagnoses]; next[i] = { ...next[i], condition: v }; setDiagnoses(next);
                  markEdit(`dx-${i}-condition`);
                }}
              />
              <EditableField
                value={dx.icd_10 || ''}
                edited={isEdited(`dx-${i}-icd10`)}
                onChange={(v) => {
                  const next = [...diagnoses]; next[i] = { ...next[i], icd_10: v || null }; setDiagnoses(next);
                  markEdit(`dx-${i}-icd10`);
                }}
                placeholder="ICD-10"
                className="font-mono text-xs px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded"
              />
              <EditableField
                value={dx.severity || ''}
                edited={isEdited(`dx-${i}-severity`)}
                onChange={(v) => {
                  const next = [...diagnoses]; next[i] = { ...next[i], severity: v || null }; setDiagnoses(next);
                  markEdit(`dx-${i}-severity`);
                }}
                placeholder="Severity"
                className="text-gray-500 text-xs"
              />
              <EditableField
                value={dx.status || ''}
                edited={isEdited(`dx-${i}-status`)}
                onChange={(v) => {
                  const next = [...diagnoses]; next[i] = { ...next[i], status: v || null }; setDiagnoses(next);
                  markEdit(`dx-${i}-status`);
                }}
                placeholder="Status"
                className="text-gray-500 text-xs"
              />
              <EditableField
                value={dx.diagnosed_date || ''}
                edited={isEdited(`dx-${i}-date`)}
                onChange={(v) => {
                  const next = [...diagnoses]; next[i] = { ...next[i], diagnosed_date: v || null }; setDiagnoses(next);
                  markEdit(`dx-${i}-date`);
                }}
                placeholder="Diagnosed date"
                className="text-gray-400 text-xs"
              />
            </RemovableRow>
          ))}
        </EditableSection>
      )}

      {/* Medication Starts */}
      {editMedStarts.length > 0 && (
        <EditableSection title="Medications — START" badgeClass="bg-green-100 text-green-700">
          {editMedStarts.map((med, i) => (
            <RemovableRow key={i} onRemove={() => removeItem(editMedStarts, i, setEditMedStarts)}>
              <EditableMedItem
                med={med}
                editPrefix={`medstart-${i}`}
                isEdited={isEdited}
                onChange={(updated) => {
                  const next = [...editMedStarts]; next[i] = updated; setEditMedStarts(next);
                }}
                markEdit={markEdit}
              />
            </RemovableRow>
          ))}
        </EditableSection>
      )}

      {/* Medication Stops */}
      {editMedStops.length > 0 && (
        <EditableSection title="Medications — STOP" badgeClass="bg-red-100 text-red-700">
          {editMedStops.map((med, i) => (
            <RemovableRow key={i} onRemove={() => removeItem(editMedStops, i, setEditMedStops)}>
              <EditableMedItem
                med={med}
                editPrefix={`medstop-${i}`}
                isEdited={isEdited}
                onChange={(updated) => {
                  const next = [...editMedStops]; next[i] = updated; setEditMedStops(next);
                }}
                markEdit={markEdit}
              />
            </RemovableRow>
          ))}
        </EditableSection>
      )}

      {/* Medication Changes (now editable) */}
      {editMedUpdates.length > 0 && (
        <EditableSection title="Medications — CHANGED" badgeClass="bg-yellow-100 text-yellow-700">
          {editMedUpdates.map((med, i) => (
            <RemovableRow key={i} onRemove={() => removeItem(editMedUpdates, i, setEditMedUpdates)}>
              <EditableMedItem
                med={med}
                editPrefix={`medupdate-${i}`}
                isEdited={isEdited}
                onChange={(updated) => {
                  const next = [...editMedUpdates]; next[i] = updated; setEditMedUpdates(next);
                }}
                markEdit={markEdit}
              />
            </RemovableRow>
          ))}
        </EditableSection>
      )}

      {/* Lab Orders */}
      {labOrders.length > 0 && (
        <EditableSection title="Lab Orders">
          {labOrders.map((lab, i) => (
            <RemovableRow key={i} onRemove={() => removeItem(labOrders, i, setLabOrders)}>
              <EditableField
                value={lab.test}
                edited={isEdited(`lab-${i}-test`)}
                onChange={(v) => {
                  const next = [...labOrders]; next[i] = { ...next[i], test: v }; setLabOrders(next);
                  markEdit(`lab-${i}-test`);
                }}
              />
              <EditableField
                value={lab.ordered_date || ''}
                edited={isEdited(`lab-${i}-date`)}
                onChange={(v) => {
                  const next = [...labOrders]; next[i] = { ...next[i], ordered_date: v || null }; setLabOrders(next);
                  markEdit(`lab-${i}-date`);
                }}
                placeholder="Date"
                className="text-gray-400 text-xs"
              />
            </RemovableRow>
          ))}
        </EditableSection>
      )}

      {/* Referrals */}
      {referrals.length > 0 && (
        <EditableSection title="Referrals">
          {referrals.map((ref, i) => (
            <RemovableRow key={i} onRemove={() => removeItem(referrals, i, setReferrals)}>
              <EditableField
                value={ref.specialty}
                edited={isEdited(`ref-${i}-specialty`)}
                onChange={(v) => {
                  const next = [...referrals]; next[i] = { ...next[i], specialty: v }; setReferrals(next);
                  markEdit(`ref-${i}-specialty`);
                }}
                className="font-medium"
              />
              <EditableField
                value={ref.provider || ''}
                edited={isEdited(`ref-${i}-provider`)}
                onChange={(v) => {
                  const next = [...referrals]; next[i] = { ...next[i], provider: v || null }; setReferrals(next);
                  markEdit(`ref-${i}-provider`);
                }}
                placeholder="Provider"
                className="text-gray-500"
              />
              <EditableField
                value={ref.reason || ''}
                edited={isEdited(`ref-${i}-reason`)}
                onChange={(v) => {
                  const next = [...referrals]; next[i] = { ...next[i], reason: v || null }; setReferrals(next);
                  markEdit(`ref-${i}-reason`);
                }}
                placeholder="Reason"
                className="text-gray-400 text-xs"
              />
            </RemovableRow>
          ))}
        </EditableSection>
      )}

      {/* Follow-ups */}
      {followUps.length > 0 && (
        <EditableSection title="Follow-up Recommendations">
          {followUps.map((fu, i) => (
            <RemovableRow key={i} onRemove={() => removeItem(followUps, i, setFollowUps)}>
              <EditableField
                value={fu.description}
                edited={isEdited(`fu-${i}-desc`)}
                onChange={(v) => {
                  const next = [...followUps]; next[i] = { ...next[i], description: v }; setFollowUps(next);
                  markEdit(`fu-${i}-desc`);
                }}
              />
              <EditableField
                value={fu.timeframe || ''}
                edited={isEdited(`fu-${i}-timeframe`)}
                onChange={(v) => {
                  const next = [...followUps]; next[i] = { ...next[i], timeframe: v || null }; setFollowUps(next);
                  markEdit(`fu-${i}-timeframe`);
                }}
                placeholder="Timeframe"
                className="text-gray-500 text-xs"
              />
              <EditableField
                value={fu.target_date || ''}
                edited={isEdited(`fu-${i}-target`)}
                onChange={(v) => {
                  const next = [...followUps]; next[i] = { ...next[i], target_date: v || null }; setFollowUps(next);
                  markEdit(`fu-${i}-target`);
                }}
                placeholder="Target date"
                className="text-gray-400 text-xs"
              />
            </RemovableRow>
          ))}
        </EditableSection>
      )}

      {/* Upcoming Appointments */}
      {appointments.length > 0 && (
        <EditableSection title="Upcoming Appointments">
          {appointments.map((appt, i) => (
            <RemovableRow key={i} onRemove={() => removeItem(appointments, i, setAppointments)}>
              <EditableField
                value={appt.description}
                edited={isEdited(`appt-${i}-desc`)}
                onChange={(v) => {
                  const next = [...appointments]; next[i] = { ...next[i], description: v }; setAppointments(next);
                  markEdit(`appt-${i}-desc`);
                }}
              />
              <EditableField
                value={appt.date || ''}
                edited={isEdited(`appt-${i}-date`)}
                onChange={(v) => {
                  const next = [...appointments]; next[i] = { ...next[i], date: v || null }; setAppointments(next);
                  markEdit(`appt-${i}-date`);
                }}
                placeholder="Date"
                className="text-gray-500 text-xs"
              />
              <EditableField
                value={appt.time || ''}
                edited={isEdited(`appt-${i}-time`)}
                onChange={(v) => {
                  const next = [...appointments]; next[i] = { ...next[i], time: v || null }; setAppointments(next);
                  markEdit(`appt-${i}-time`);
                }}
                placeholder="Time"
                className="text-gray-400 text-xs"
              />
              <EditableField
                value={appt.location || ''}
                edited={isEdited(`appt-${i}-loc`)}
                onChange={(v) => {
                  const next = [...appointments]; next[i] = { ...next[i], location: v || null }; setAppointments(next);
                  markEdit(`appt-${i}-loc`);
                }}
                placeholder="Location"
                className="text-gray-400 text-xs"
              />
            </RemovableRow>
          ))}
        </EditableSection>
      )}

      {/* Notes (editable, reference only) */}
      {notes.length > 0 && (
        <EditableSection title="Notes & Instructions" subtitle="For reference — not saved to profile">
          {notes.map((note, i) => (
            <RemovableRow key={i} onRemove={() => removeItem(notes, i, setNotes)}>
              <EditableField
                value={note}
                edited={isEdited(`note-${i}`)}
                onChange={(v) => {
                  const next = [...notes]; next[i] = v; setNotes(next);
                  markEdit(`note-${i}`);
                }}
              />
            </RemovableRow>
          ))}
        </EditableSection>
      )}

      {/* Action buttons */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-200">
        <div className="text-sm text-gray-500">
          {totalItems} item{totalItems !== 1 ? 's' : ''} to apply
          {editCount > 0 && (
            <span className="ml-2 text-amber-600">
              ({editCount} edit{editCount !== 1 ? 's' : ''} made)
            </span>
          )}
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={onBack}>Cancel</Button>
          <Button onClick={openConfirm} disabled={isApplying || isPreviewing || totalItems === 0}>
            {isApplying ? 'Applying...' : isPreviewing ? 'Checking...' : 'Review Changes'}
          </Button>
        </div>
      </div>

      {/* Confirmation modal */}
      <Modal isOpen={showConfirm} onClose={() => setShowConfirm(false)} title="Confirm Profile Update">
        <div className="space-y-4">
          {stalePlan && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
              <span className="font-medium">This profile changed while you were reviewing.</span>{' '}
              Nothing was saved. The changes below have been recalculated against your current
              profile — check them again before confirming.
            </div>
          )}

          {isPreviewing && (
            <p className="text-sm text-gray-500">Working out what would change...</p>
          )}

          {planError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
              {planError}
            </div>
          )}

          {displayPlan && (
            <>
              <p className="text-sm text-gray-600">
                {updateEntries.length > 0
                  ? 'Some of these replace values already in your profile. Replaced values are not recoverable, so check them before confirming.'
                  : 'Here is exactly what will change in your profile:'}
              </p>

              <div className="bg-gray-50 rounded-lg p-4 space-y-4 text-sm max-h-80 overflow-y-auto">
                {updateEntries.length > 0 && (
                  <PlanGroup
                    title="Will be changed"
                    caption="existing entries whose values get replaced"
                    entries={updateEntries}
                    tone="amber"
                  />
                )}
                {createEntries.length > 0 && (
                  <PlanGroup
                    title="Will be added"
                    caption="new entries in your profile"
                    entries={createEntries}
                    tone="teal"
                  />
                )}
                {skipEntries.length > 0 && (
                  <PlanGroup
                    title="Will be left alone"
                    caption="nothing in your profile changes for these"
                    entries={skipEntries}
                    tone="gray"
                  />
                )}
                {displayPlan.entries.length === 0 && (
                  <p className="text-gray-500">Nothing in your profile would change.</p>
                )}
              </div>
            </>
          )}

          {notes.length > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
              <span className="font-medium">Notes & Instructions</span> are shown for your review but will not be saved to the profile.
            </div>
          )}

          {editCount > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800 flex items-start gap-2">
              <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
              </svg>
              <span>You made {editCount} edit{editCount !== 1 ? 's' : ''} to the extracted data before this step.</span>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowConfirm(false)}>Go Back</Button>
            <Button onClick={handleConfirmApply} disabled={isApplying || isPreviewing || !displayPlan}>
              {isApplying ? 'Applying...' : 'Yes, Update Profile'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ── Editable Section wrapper ──

function EditableSection({
  title,
  subtitle,
  badgeClass,
  children,
}: {
  title: string;
  subtitle?: string;
  badgeClass?: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <div>
          <h4 className="font-semibold text-gray-900">
            {title}
            {badgeClass && (
              <span className={`ml-2 px-1.5 py-0.5 rounded text-xs font-medium ${badgeClass}`}>
                {title.split('—')[1]?.trim()}
              </span>
            )}
          </h4>
          {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {children}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Removable Row: item with X button ──

function RemovableRow({
  onRemove,
  children,
}: {
  onRemove: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 group">
      <div className="text-sm text-gray-700 flex-1 flex items-center gap-2 flex-wrap">
        {children}
      </div>
      <button
        onClick={onRemove}
        title="Remove item"
        className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-red-500 p-0.5 -mt-0.5 flex-shrink-0"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

// ── Editable field: click to edit, highlights when modified ──

function EditableField({
  value,
  edited,
  onChange,
  placeholder,
  className = '',
}: {
  value: string;
  edited: boolean;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const [editing, setEditing] = useState(false);

  if (editing) {
    return (
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={() => setEditing(false)}
        onKeyDown={(e) => { if (e.key === 'Enter') setEditing(false); }}
        autoFocus
        className={`border border-brand-teal-bright/40 rounded px-1.5 py-0.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-teal-bright ${edited ? 'bg-amber-50' : 'bg-white'} ${className}`}
        placeholder={placeholder}
      />
    );
  }

  return (
    <span
      onClick={() => setEditing(true)}
      title="Click to edit"
      className={`cursor-pointer rounded px-1 py-0.5 transition-colors hover:bg-gray-100 ${edited ? 'bg-amber-100 ring-1 ring-amber-300' : ''} ${className}`}
    >
      {value || <span className="text-gray-300 italic">{placeholder || 'empty'}</span>}
    </span>
  );
}

// ── Editable vital field ──

function EditableVital({
  label,
  value,
  edited,
  onChange,
}: {
  label: string;
  value: string;
  edited: boolean;
  onChange: (value: string) => void;
}) {
  const [editing, setEditing] = useState(false);

  return (
    <div>
      <span className="text-gray-500">{label}</span>
      {editing ? (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={() => setEditing(false)}
          onKeyDown={(e) => { if (e.key === 'Enter') setEditing(false); }}
          autoFocus
          className={`block w-full mt-0.5 border border-brand-teal-bright/40 rounded px-1.5 py-0.5 text-sm font-medium focus:outline-none focus:ring-1 focus:ring-brand-teal-bright ${edited ? 'bg-amber-50' : 'bg-white'}`}
        />
      ) : (
        <p
          onClick={() => setEditing(true)}
          title="Click to edit"
          className={`font-medium text-gray-900 cursor-pointer rounded px-1 py-0.5 transition-colors hover:bg-gray-100 ${edited ? 'bg-amber-100 ring-1 ring-amber-300' : ''}`}
        >
          {value}
        </p>
      )}
    </div>
  );
}

// ── Editable medication item ──

function EditableMedItem({
  med,
  editPrefix,
  isEdited,
  onChange,
  markEdit,
}: {
  med: ParsedMedicationChange;
  editPrefix: string;
  isEdited: (key: string) => boolean;
  onChange: (updated: ParsedMedicationChange) => void;
  markEdit: (key: string) => void;
}) {
  return (
    <>
      <EditableField
        value={med.name}
        edited={isEdited(`${editPrefix}-name`)}
        onChange={(v) => { onChange({ ...med, name: v }); markEdit(`${editPrefix}-name`); }}
        className="font-medium"
      />
      {med.strength && (
        <EditableField
          value={med.strength}
          edited={isEdited(`${editPrefix}-strength`)}
          onChange={(v) => { onChange({ ...med, strength: v || null }); markEdit(`${editPrefix}-strength`); }}
          className="text-gray-500 text-xs"
        />
      )}
      {med.instructions && (
        <EditableField
          value={med.instructions}
          edited={isEdited(`${editPrefix}-instr`)}
          onChange={(v) => { onChange({ ...med, instructions: v || null }); markEdit(`${editPrefix}-instr`); }}
          className="text-gray-400 text-xs"
        />
      )}
    </>
  );
}

// ── Pre-apply diff (issue #46) ──

const PLAN_TONES = {
  amber: 'border-amber-300 bg-amber-50',
  teal: 'border-brand-teal-bright/40 bg-white',
  gray: 'border-gray-200 bg-white',
} as const;

function PlanGroup({
  title,
  caption,
  entries,
  tone,
}: {
  title: string;
  caption: string;
  entries: ApplyPlanEntry[];
  tone: keyof typeof PLAN_TONES;
}) {
  return (
    <div>
      <p className="font-medium text-gray-700">
        {title} ({entries.length})
        <span className="font-normal text-gray-500"> — {caption}</span>
      </p>
      <ul className="mt-1 space-y-1.5">
        {entries.map((entry, i) => (
          <li key={`${entry.entity_type}-${entry.entity_id ?? i}`}
              className={`border rounded px-2 py-1.5 ${PLAN_TONES[tone]}`}>
            <div className="flex items-baseline gap-1.5">
              <span className="text-xs uppercase tracking-wide text-gray-400 flex-shrink-0">
                {ENTITY_LABELS[entry.entity_type] ?? entry.entity_type}
              </span>
              <span className="font-medium text-gray-900">{entry.label}</span>
            </div>
            {entry.reason && (
              <p className="text-xs text-gray-500 mt-0.5">{entry.reason}</p>
            )}
            <PlanChanges entry={entry} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function PlanChanges({ entry }: { entry: ApplyPlanEntry }) {
  // Fields the AVS repeats back unchanged are noise in a diff — count them,
  // but only show what actually differs.
  const changed = entry.changes.filter(c => c.changed);
  const unchanged = entry.changes.length - changed.length;

  if (entry.changes.length === 0) return null;

  return (
    <div className="mt-1 space-y-0.5">
      {changed.map(change => (
        <div key={change.field} className="text-xs text-gray-600 flex flex-wrap items-baseline gap-1">
          <span className="text-gray-500">{change.field.replace(/_/g, ' ')}:</span>
          {entry.action === 'update' && (
            <>
              <span className="line-through text-red-700/70">{change.old_value ?? '(empty)'}</span>
              <span aria-hidden="true">→</span>
            </>
          )}
          <span className="font-medium text-gray-900">{change.new_value ?? '(empty)'}</span>
        </div>
      ))}
      {unchanged > 0 && (
        <p className="text-xs text-gray-400">
          {unchanged} field{unchanged !== 1 ? 's' : ''} already match{unchanged === 1 ? 'es' : ''} — unchanged
        </p>
      )}
    </div>
  );
}
