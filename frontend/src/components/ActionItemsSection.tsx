import { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { actionItems as actionItemsApi } from '../api/client';
import { Card, CardHeader, CardContent } from './Card';
import type { Appointment, Doctor, FollowUp, LabOrder, Referral, SnoozedItem } from '../types';

// Categories backed by NudgeState (a computed nudge with no row of its own)
// vs. a model row (FollowUp/LabOrder/Referral) that carries snoozed_until
// directly — un-snoozing each needs a different API call (issue #44).
const NUDGE_CATEGORIES = new Set(['past_due', 'upcoming_without_prep', 'completed_without_avs', 'vitals_alert']);

interface Props {
  profileId: string;
  appointments: Appointment[];
  doctors: Doctor[];
}

function daysUntil(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
}

function daysSince(dateStr: string): number {
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / (1000 * 60 * 60 * 24));
}

function soonestUpcomingAppointment(appointments: Appointment[]): Appointment | null {
  const now = new Date();
  const future = appointments
    .filter(a => a.status === 'scheduled' && new Date(a.scheduled_date) > now)
    .sort((a, b) => new Date(a.scheduled_date).getTime() - new Date(b.scheduled_date).getTime());
  return future[0] ?? null;
}

function timeframeToDays(timeframe: string): number | null {
  const t = timeframe.toLowerCase();
  const match = t.match(/(\d+)\s*(day|week|month|year)/);
  if (!match) return null;
  const n = parseInt(match[1]);
  const unit = match[2];
  if (unit === 'day') return n;
  if (unit === 'week') return n * 7;
  if (unit === 'month') return n * 30;
  if (unit === 'year') return n * 365;
  return null;
}

function followUpOverdueFraction(createdAt: string, timeframe: string | null): number | null {
  if (!timeframe) return null;
  const days = timeframeToDays(timeframe);
  if (!days) return null;
  return daysSince(createdAt) / days;
}

// Gap 3: flexible snooze durations
const SNOOZE_OPTIONS = [
  { label: '1w', days: 7 },
  { label: '2w', days: 14 },
  { label: '1m', days: 30 },
];

function snoozeDate(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

// Gap 2: badge shown when item previously had a snooze that has expired
function PreviouslySnoozedBadge({ item }: { item: FollowUp | LabOrder | Referral }) {
  if (!item.snoozed_until) return null;
  return (
    <span className="inline-flex items-center gap-0.5 text-xs text-gray-400 ml-1">
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      snoozed
    </span>
  );
}

// Gap 3: pill group replacing single "Snooze 1w" button
function SnoozeButtons({ onSnooze, isPending }: { onSnooze: (days: number) => void; isPending: boolean }) {
  return (
    <div className="flex flex-shrink-0">
      {SNOOZE_OPTIONS.map((opt, i) => (
        <button
          key={opt.label}
          onClick={() => onSnooze(opt.days)}
          disabled={isPending}
          className={`text-xs px-2 py-1 text-gray-400 border border-gray-200 hover:bg-gray-50 disabled:opacity-50
            ${i === 0 ? 'rounded-l' : ''} ${i === SNOOZE_OPTIONS.length - 1 ? 'rounded-r' : ''} ${i > 0 ? '-ml-px' : ''}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// Combined action + snooze pill group
function ActionButtons({
  onAction,
  onSnooze,
  actionLabel,
  isPending,
}: {
  onAction: () => void;
  onSnooze: (days: number) => void;
  actionLabel: string;
  isPending: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5 flex-shrink-0">
      <SnoozeButtons onSnooze={onSnooze} isPending={isPending} />
      <button
        onClick={onAction}
        disabled={isPending}
        className="text-xs px-2.5 py-1 bg-brand-teal-bright text-white rounded hover:bg-brand-teal disabled:opacity-50"
      >
        {actionLabel}
      </button>
    </div>
  );
}

// Gap 1: resolved items section
function ResolvedItems({
  followUps,
  labOrders,
  referrals,
}: {
  followUps: FollowUp[];
  labOrders: LabOrder[];
  referrals: Referral[];
}) {
  if (!followUps.length && !labOrders.length && !referrals.length) {
    return <p className="text-sm text-gray-400 italic">No resolved items yet.</p>;
  }
  return (
    <div className="space-y-3">
      {followUps.map(fu => (
        <div key={fu.id} className="flex items-start justify-between gap-2 bg-white rounded border border-gray-100 px-3 py-2 opacity-60">
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-600 line-through">{fu.description}</p>
            {fu.completed_at && (
              <p className="text-xs text-gray-400 mt-0.5">
                Completed {new Date(fu.completed_at).toLocaleDateString()}
              </p>
            )}
          </div>
          <span className="text-xs text-gray-400 flex-shrink-0">{fu.status}</span>
        </div>
      ))}
      {labOrders.map(lab => (
        <div key={lab.id} className="flex items-start justify-between gap-2 bg-white rounded border border-gray-100 px-3 py-2 opacity-60">
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-600 line-through">{lab.test_name}</p>
            {lab.completed_at && (
              <p className="text-xs text-gray-400 mt-0.5">
                Completed {new Date(lab.completed_at).toLocaleDateString()}
              </p>
            )}
          </div>
          <span className="text-xs text-gray-400 flex-shrink-0">{lab.status}</span>
        </div>
      ))}
      {referrals.map(ref => (
        <div key={ref.id} className="flex items-start justify-between gap-2 bg-white rounded border border-gray-100 px-3 py-2 opacity-60">
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-600 line-through">{ref.specialty}{ref.provider_name ? ` — ${ref.provider_name}` : ''}</p>
            {ref.completed_at && (
              <p className="text-xs text-gray-400 mt-0.5">
                Completed {new Date(ref.completed_at).toLocaleDateString()}
              </p>
            )}
          </div>
          <span className="text-xs text-gray-400 flex-shrink-0">{ref.status}</span>
        </div>
      ))}
    </div>
  );
}

function formatSnoozedUntil(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// Issue #44: currently-snoozed items had no view anywhere in the UI — this
// makes them visible with an early "un-snooze now" per item.
function SnoozedItemsList({
  items,
  onUnsnooze,
  isPending,
}: {
  items: SnoozedItem[];
  onUnsnooze: (item: SnoozedItem) => void;
  isPending: boolean;
}) {
  if (!items.length) {
    return <p className="text-sm text-gray-400 italic">Nothing currently snoozed.</p>;
  }
  return (
    <div className="space-y-2">
      {items.map(item => (
        <div key={`${item.category}-${item.item_id}`} className="flex items-center justify-between gap-2 bg-white rounded border border-gray-100 px-3 py-2">
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-700">{item.label}</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {item.category_label} — snoozed until {formatSnoozedUntil(item.snoozed_until)}
            </p>
          </div>
          <button
            onClick={() => onUnsnooze(item)}
            disabled={isPending}
            className="text-xs px-2.5 py-1 border border-gray-300 text-gray-600 rounded hover:bg-gray-50 disabled:opacity-50 flex-shrink-0"
          >
            Un-snooze now
          </button>
        </div>
      ))}
    </div>
  );
}

// Issue #44: a snooze pill fired immediately with no confirmation and no
// undo — one misclick removed an item from view with no recovery path.
function UndoSnoozeBanner({ label, onUndo }: { label: string; onUndo: () => void }) {
  return (
    <div className="flex items-center justify-between gap-2 bg-gray-800 text-white text-sm rounded-lg px-3 py-2">
      <span>Snoozed "{label}"</span>
      <button onClick={onUndo} className="text-xs font-medium underline underline-offset-2 hover:text-gray-200 flex-shrink-0">
        Undo
      </button>
    </div>
  );
}

export function ActionItemsSection({ profileId, appointments, doctors }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Gap 1: toggle for resolved history
  const [showResolved, setShowResolved] = useState(false);
  // Issue #44: toggle for currently-snoozed items
  const [showSnoozed, setShowSnoozed] = useState(false);
  const [undoBanner, setUndoBanner] = useState<{ category: string; itemId: string; label: string } | null>(null);
  const undoTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const invalidateFollowUps = () => queryClient.invalidateQueries({ queryKey: ['followUps', profileId] });
  const invalidateLabOrders = () => queryClient.invalidateQueries({ queryKey: ['labOrders', profileId] });
  const invalidateReferrals = () => queryClient.invalidateQueries({ queryKey: ['referrals', profileId] });
  const invalidatePastDue = () => queryClient.invalidateQueries({ queryKey: ['pastDueAppointments', profileId] });
  const invalidateUpcomingPrep = () => queryClient.invalidateQueries({ queryKey: ['upcomingWithoutPrep', profileId] });
  const invalidateVitals = () => queryClient.invalidateQueries({ queryKey: ['vitalsAlerts', profileId] });
  const invalidateCompletedAvs = () => queryClient.invalidateQueries({ queryKey: ['completedWithoutAvs', profileId] });
  const invalidateSnoozedItems = () => queryClient.invalidateQueries({ queryKey: ['snoozedItems', profileId] });

  // Issue #44: shows an undo banner for ~8s after any snooze action; calling
  // it again (a second snooze while one banner is showing) replaces it
  // rather than stacking, matching how a single-slot toast would behave.
  const showUndoBanner = (category: string, itemId: string, label: string) => {
    if (undoTimeoutRef.current) clearTimeout(undoTimeoutRef.current);
    setUndoBanner({ category, itemId, label });
    undoTimeoutRef.current = setTimeout(() => setUndoBanner(null), 8000);
  };

  const { data: followUps = [] } = useQuery({
    queryKey: ['followUps', profileId],
    queryFn: () => actionItemsApi.listFollowUps(profileId),
    enabled: !!profileId,
  });

  const { data: labOrders = [] } = useQuery({
    queryKey: ['labOrders', profileId],
    queryFn: () => actionItemsApi.listLabOrders(profileId),
    enabled: !!profileId,
  });

  const { data: referrals = [] } = useQuery({
    queryKey: ['referrals', profileId],
    queryFn: () => actionItemsApi.listReferrals(profileId),
    enabled: !!profileId,
  });

  // Gap 1: resolved queries — only fire when toggle is on
  const { data: resolvedFollowUps = [] } = useQuery({
    queryKey: ['followUpsResolved', profileId],
    queryFn: () => actionItemsApi.listFollowUps(profileId, undefined, true),
    enabled: !!profileId && showResolved,
  });

  const { data: resolvedLabOrders = [] } = useQuery({
    queryKey: ['labOrdersResolved', profileId],
    queryFn: () => actionItemsApi.listLabOrders(profileId, undefined, true),
    enabled: !!profileId && showResolved,
  });

  const { data: resolvedReferrals = [] } = useQuery({
    queryKey: ['referralsResolved', profileId],
    queryFn: () => actionItemsApi.listReferrals(profileId, undefined, true),
    enabled: !!profileId && showResolved,
  });

  const { data: pastDueFromServer = [] } = useQuery({
    queryKey: ['pastDueAppointments', profileId],
    queryFn: () => actionItemsApi.pastDueAppointments(profileId),
    enabled: !!profileId,
  });

  const { data: unpreparedAppointments = [] } = useQuery({
    queryKey: ['upcomingWithoutPrep', profileId],
    queryFn: () => actionItemsApi.upcomingWithoutPrep(profileId),
    enabled: !!profileId,
  });

  const { data: vitalsAlerts = [] } = useQuery({
    queryKey: ['vitalsAlerts', profileId],
    queryFn: () => actionItemsApi.vitalsAlerts(profileId),
    enabled: !!profileId,
  });

  const { data: completedWithoutAvs = [] } = useQuery({
    queryKey: ['completedWithoutAvs', profileId],
    queryFn: () => actionItemsApi.completedWithoutAvs(profileId),
    enabled: !!profileId,
  });

  // Issue #44: unified view of everything currently snoozed, across both
  // NudgeState-backed computed nudges and FollowUp/LabOrder/Referral rows.
  const { data: snoozedItems = [] } = useQuery({
    queryKey: ['snoozedItems', profileId],
    queryFn: () => actionItemsApi.listSnoozedItems(profileId),
    enabled: !!profileId && showSnoozed,
  });

  const followUpMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof actionItemsApi.updateFollowUp>[2] }) =>
      actionItemsApi.updateFollowUp(profileId, id, body),
    onSuccess: () => {
      invalidateFollowUps();
      queryClient.invalidateQueries({ queryKey: ['followUpsResolved', profileId] });
      invalidateSnoozedItems();
    },
  });

  const labMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof actionItemsApi.updateLabOrder>[2] }) =>
      actionItemsApi.updateLabOrder(profileId, id, body),
    onSuccess: () => {
      invalidateLabOrders();
      queryClient.invalidateQueries({ queryKey: ['labOrdersResolved', profileId] });
      invalidateSnoozedItems();
    },
  });

  const referralMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof actionItemsApi.updateReferral>[2] }) =>
      actionItemsApi.updateReferral(profileId, id, body),
    onSuccess: () => {
      invalidateReferrals();
      queryClient.invalidateQueries({ queryKey: ['referralsResolved', profileId] });
      invalidateSnoozedItems();
    },
  });

  const snoozePrepMutation = useMutation({
    mutationFn: ({ id, days }: { id: string; days: number }) =>
      actionItemsApi.snoozeNudge(profileId, 'upcoming_without_prep', id, snoozeDate(days)),
    onSuccess: () => { invalidateUpcomingPrep(); invalidateSnoozedItems(); },
  });

  const snoozePastDueMutation = useMutation({
    mutationFn: ({ id, days }: { id: string; days: number }) =>
      actionItemsApi.snoozeNudge(profileId, 'past_due', id, snoozeDate(days)),
    onSuccess: () => { invalidatePastDue(); invalidateSnoozedItems(); },
  });

  const snoozeVitalsMutation = useMutation({
    mutationFn: ({ metric, days }: { metric: string; days: number }) =>
      actionItemsApi.snoozeNudge(profileId, 'vitals_alert', metric, snoozeDate(days)),
    onSuccess: () => { invalidateVitals(); invalidateSnoozedItems(); },
  });

  const snoozeAvsCompletedMutation = useMutation({
    mutationFn: ({ id, days }: { id: string; days: number }) =>
      actionItemsApi.snoozeNudge(profileId, 'completed_without_avs', id, snoozeDate(days)),
    onSuccess: () => { invalidateCompletedAvs(); invalidateSnoozedItems(); },
  });

  // Issue #44: un-snooze early, from either the "Snoozed" list's per-item
  // button or the undo banner. Dispatches to the right API call since
  // NudgeState-backed nudges (no snoozed_until on a row of their own) and
  // model rows (FollowUp/LabOrder/Referral) un-snooze differently.
  const unsnoozeMutation = useMutation({
    mutationFn: ({ category, itemId }: { category: string; itemId: string }) => {
      if (NUDGE_CATEGORIES.has(category)) {
        return actionItemsApi.unsnoozeNudge(profileId, category, itemId);
      }
      const updaters: Record<string, (id: string) => Promise<unknown>> = {
        follow_up: (id) => actionItemsApi.updateFollowUp(profileId, id, { snoozed_until: null }),
        lab_order: (id) => actionItemsApi.updateLabOrder(profileId, id, { snoozed_until: null }),
        referral: (id) => actionItemsApi.updateReferral(profileId, id, { snoozed_until: null }),
      };
      return updaters[category](itemId);
    },
    onSuccess: (_data, { category }) => {
      invalidateSnoozedItems();
      if (category === 'upcoming_without_prep') invalidateUpcomingPrep();
      else if (category === 'past_due') invalidatePastDue();
      else if (category === 'vitals_alert') invalidateVitals();
      else if (category === 'completed_without_avs') invalidateCompletedAvs();
      else if (category === 'follow_up') { invalidateFollowUps(); queryClient.invalidateQueries({ queryKey: ['followUpsResolved', profileId] }); }
      else if (category === 'lab_order') { invalidateLabOrders(); queryClient.invalidateQueries({ queryKey: ['labOrdersResolved', profileId] }); }
      else if (category === 'referral') { invalidateReferrals(); queryClient.invalidateQueries({ queryKey: ['referralsResolved', profileId] }); }
    },
  });

  const total =
    unpreparedAppointments.length +
    pastDueFromServer.length +
    completedWithoutAvs.length +
    vitalsAlerts.length +
    followUps.length +
    labOrders.length +
    referrals.length;

  if (total === 0 && !showResolved && !showSnoozed) return null;

  const nextAppt = soonestUpcomingAppointment(appointments);
  const daysToAppt = nextAppt ? daysUntil(nextAppt.scheduled_date) : null;

  return (
    <Card className="border-orange-200 bg-orange-50">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {total > 0 && (
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-orange-500 text-white text-xs font-bold">
                {total}
              </span>
            )}
            <h3 className="font-semibold text-orange-900">
              {total > 0 ? 'Needs Attention' : 'Action Items'}
            </h3>
          </div>
          <div className="flex items-center gap-3">
            {/* Issue #44: currently-snoozed toggle */}
            <button
              onClick={() => setShowSnoozed(v => !v)}
              className="text-xs text-gray-500 hover:text-gray-700 underline underline-offset-2"
            >
              {showSnoozed ? 'Hide snoozed' : 'Show snoozed'}
            </button>
            {/* Gap 1: resolved toggle */}
            <button
              onClick={() => setShowResolved(v => !v)}
              className="text-xs text-gray-500 hover:text-gray-700 underline underline-offset-2"
            >
              {showResolved ? 'Hide resolved' : 'Show resolved'}
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">

        {/* Issue #44: undo banner shown briefly after any snooze action */}
        {undoBanner && (
          <UndoSnoozeBanner
            label={undoBanner.label}
            onUndo={() => {
              unsnoozeMutation.mutate({ category: undoBanner.category, itemId: undoBanner.itemId });
              setUndoBanner(null);
            }}
          />
        )}

        {/* Issue #44: currently-snoozed items */}
        {showSnoozed && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Currently snoozed</p>
            <SnoozedItemsList
              items={snoozedItems}
              onUnsnooze={(item) => unsnoozeMutation.mutate({ category: item.category, itemId: item.item_id })}
              isPending={unsnoozeMutation.isPending}
            />
            {total > 0 && <hr className="border-orange-200 mt-3" />}
          </div>
        )}

        {/* Gap 1: resolved history */}
        {showResolved && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Resolved (last 20)</p>
            <ResolvedItems
              followUps={resolvedFollowUps}
              labOrders={resolvedLabOrders}
              referrals={resolvedReferrals}
            />
            {total > 0 && <hr className="border-orange-200 mt-3" />}
          </div>
        )}

        {/* Visit prep nudge */}
        {unpreparedAppointments.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Visit prep needed</p>
            {unpreparedAppointments.map(appt => {
              const doctor = doctors.find(d => d.id === appt.doctor_id);
              const label = doctor ? doctor.name : appt.purpose || 'Appointment';
              const days = daysUntil(appt.scheduled_date);
              return (
                <div key={appt.id} className="flex items-center justify-between gap-2 bg-white rounded border border-orange-100 px-3 py-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{label}</p>
                    <p className="text-xs text-orange-600 font-medium mt-0.5">
                      in {days} day{days !== 1 ? 's' : ''} — no prep generated yet
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <SnoozeButtons
                      onSnooze={(d) => snoozePrepMutation.mutate(
                        { id: appt.id, days: d },
                        { onSuccess: () => showUndoBanner('upcoming_without_prep', appt.id, label) },
                      )}
                      isPending={snoozePrepMutation.isPending}
                    />
                    <button
                      onClick={() => navigate(`/profiles/${profileId}/appointments/${appt.id}/prep`)}
                      className="text-xs px-2.5 py-1 bg-brand-teal-bright text-white rounded hover:bg-brand-teal flex-shrink-0"
                    >
                      Prepare
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Past-due appointments not marked complete */}
        {pastDueFromServer.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Appointments to close out</p>
            {pastDueFromServer.map(appt => {
              const doctor = doctors.find(d => d.id === appt.doctor_id);
              const label = doctor ? doctor.name : appt.purpose || 'Appointment';
              const ago = daysSince(appt.scheduled_date);
              return (
                <div key={appt.id} className="flex items-center justify-between gap-2 bg-white rounded border border-orange-100 px-3 py-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{label}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {ago} day{ago !== 1 ? 's' : ''} ago — not marked complete
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <SnoozeButtons
                      onSnooze={(d) => snoozePastDueMutation.mutate(
                        { id: appt.id, days: d },
                        { onSuccess: () => showUndoBanner('past_due', appt.id, label) },
                      )}
                      isPending={snoozePastDueMutation.isPending}
                    />
                    <button
                      onClick={() => navigate(`/profiles/${profileId}/appointments/${appt.id}/prep`)}
                      className="text-xs px-2.5 py-1 bg-gray-600 text-white rounded hover:bg-gray-700"
                    >
                      Add notes
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Completed appointments without AVS */}
        {completedWithoutAvs.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Missing after-visit summaries</p>
            {completedWithoutAvs.map(appt => {
              const doctor = doctors.find(d => d.id === appt.doctor_id);
              const label = doctor ? doctor.name : appt.purpose || 'Appointment';
              return (
                <div key={appt.id} className="flex items-start gap-2 bg-white rounded border border-orange-100 px-3 py-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{label}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {new Date(appt.scheduled_date).toLocaleDateString()} — no AVS parsed for this visit
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">Drop the PDF in <code className="bg-gray-100 px-1 rounded">data/avs/</code> to update your profile</p>
                  </div>
                  <SnoozeButtons
                    onSnooze={(d) => snoozeAvsCompletedMutation.mutate(
                      { id: appt.id, days: d },
                      { onSuccess: () => showUndoBanner('completed_without_avs', appt.id, label) },
                    )}
                    isPending={snoozeAvsCompletedMutation.isPending}
                  />
                </div>
              );
            })}
          </div>
        )}

        {/* Vitals trend alerts */}
        {vitalsAlerts.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Vitals trends to discuss</p>
            {vitalsAlerts.map((alert, i) => (
              <div key={i} className="flex items-start gap-2 bg-white rounded border border-orange-100 px-3 py-2">
                <span className="text-base flex-shrink-0 mt-0.5">
                  {alert.direction === 'up' ? '↑' : '↓'}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800">{alert.message}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {alert.oldest_value} → {alert.newest_value} over {alert.visit_count} visits — bring this up at your next appointment
                  </p>
                </div>
                <SnoozeButtons
                  onSnooze={(d) => snoozeVitalsMutation.mutate(
                    { metric: alert.metric, days: d },
                    { onSuccess: () => showUndoBanner('vitals_alert', alert.metric, alert.metric) },
                  )}
                  isPending={snoozeVitalsMutation.isPending}
                />
              </div>
            ))}
          </div>
        )}

        {/* Follow-ups with aging */}
        {followUps.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Follow-up appointments</p>
            {followUps.map(fu => {
              const overdue = followUpOverdueFraction(fu.created_at, fu.timeframe);
              const isStale = overdue !== null && overdue >= 0.75;
              const isOverdue = overdue !== null && overdue >= 1.0;
              return (
                <div key={fu.id} className={`flex items-start justify-between gap-2 bg-white rounded border px-3 py-2 ${isOverdue ? 'border-red-200' : isStale ? 'border-orange-200' : 'border-orange-100'}`}>
                  <div className="flex-1 min-w-0">
                    {/* Gap 2: previously snoozed badge */}
                    <p className="text-sm text-gray-800">
                      {fu.description}
                      <PreviouslySnoozedBadge item={fu} />
                    </p>
                    {fu.timeframe && (
                      <p className={`text-xs mt-0.5 ${isOverdue ? 'text-red-600 font-medium' : isStale ? 'text-orange-600' : 'text-gray-500'}`}>
                        {isOverdue ? 'Overdue — ' : isStale ? 'Approaching deadline — ' : ''}{fu.timeframe}
                      </p>
                    )}
                  </div>
                  <ActionButtons
                    onAction={() => followUpMutation.mutate({ id: fu.id, body: { status: 'booked' } })}
                    onSnooze={(days) => followUpMutation.mutate(
                      { id: fu.id, body: { snoozed_until: snoozeDate(days) } },
                      { onSuccess: () => showUndoBanner('follow_up', fu.id, fu.description) },
                    )}
                    actionLabel="Booked"
                    isPending={followUpMutation.isPending}
                  />
                </div>
              );
            })}
          </div>
        )}

        {/* Lab orders */}
        {labOrders.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">
              Lab tests ordered
              {daysToAppt !== null && daysToAppt <= 21 && (
                <span className="ml-2 font-normal normal-case text-orange-600">
                  — get done before your appointment in {daysToAppt} days
                </span>
              )}
            </p>
            {labOrders.map(lab => {
              const age = daysSince(lab.created_at);
              const isStale = age >= 21;
              return (
                <div key={lab.id} className={`flex items-center justify-between gap-2 bg-white rounded border px-3 py-2 ${isStale ? 'border-orange-200' : 'border-orange-100'}`}>
                  <div className="flex-1 min-w-0">
                    {/* Gap 2: previously snoozed badge */}
                    <p className="text-sm text-gray-800">
                      {lab.test_name}
                      <PreviouslySnoozedBadge item={lab} />
                    </p>
                    <p className={`text-xs mt-0.5 ${isStale ? 'text-orange-600' : 'text-gray-500'}`}>
                      {isStale ? `Ordered ${age} days ago — results take ~1 week` : lab.ordered_date ? `Ordered ${lab.ordered_date}` : null}
                    </p>
                  </div>
                  <ActionButtons
                    onAction={() => labMutation.mutate({ id: lab.id, body: { status: 'completed' } })}
                    onSnooze={(days) => labMutation.mutate(
                      { id: lab.id, body: { snoozed_until: snoozeDate(days) } },
                      { onSuccess: () => showUndoBanner('lab_order', lab.id, lab.test_name) },
                    )}
                    actionLabel="Done"
                    isPending={labMutation.isPending}
                  />
                </div>
              );
            })}
          </div>
        )}

        {/* Referrals with aging */}
        {referrals.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Referrals to schedule</p>
            {referrals.map(ref => {
              const age = daysSince(ref.created_at);
              const isStale = age >= 60;
              return (
                <div key={ref.id} className={`flex items-start justify-between gap-2 bg-white rounded border px-3 py-2 ${isStale ? 'border-orange-200' : 'border-orange-100'}`}>
                  <div className="flex-1 min-w-0">
                    {/* Gap 2: previously snoozed badge */}
                    <p className="text-sm text-gray-800">
                      {ref.specialty}{ref.provider_name ? ` — ${ref.provider_name}` : ''}
                      <PreviouslySnoozedBadge item={ref} />
                    </p>
                    {ref.reason && <p className="text-xs text-gray-500 mt-0.5">{ref.reason}</p>}
                    {isStale && (
                      <p className="text-xs text-orange-600 mt-0.5">Pending for {age} days</p>
                    )}
                  </div>
                  <ActionButtons
                    onAction={() => referralMutation.mutate({ id: ref.id, body: { status: 'scheduled' } })}
                    onSnooze={(days) => referralMutation.mutate(
                      { id: ref.id, body: { snoozed_until: snoozeDate(days) } },
                      { onSuccess: () => showUndoBanner('referral', ref.id, `${ref.specialty}${ref.provider_name ? ` — ${ref.provider_name}` : ''}`) },
                    )}
                    actionLabel="Scheduled"
                    isPending={referralMutation.isPending}
                  />
                </div>
              );
            })}
          </div>
        )}

      </CardContent>
    </Card>
  );
}
