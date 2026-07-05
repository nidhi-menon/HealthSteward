import { useMutation, useQueryClient } from '@tanstack/react-query';
import { actionItems as actionItemsApi } from '../api/client';
import type { ActionItems, FollowUp, LabOrder, Referral, Appointment } from '../types';

interface Props {
  profileId: string;
  actionItems: ActionItems;
  upcomingAppointments: Appointment[];
  onDismiss: () => void;
}

// Parse a free-text timeframe like "3 months", "6 weeks", "1 year" into days.
// Returns null if unparseable.
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

// Returns true if the follow-up timeframe is within 6 months.
function isUrgentFollowUp(fu: FollowUp): boolean {
  if (fu.timeframe) {
    const days = timeframeToDays(fu.timeframe);
    if (days !== null) return days <= 180;
  }
  return false;
}

// Find the soonest upcoming appointment (future, scheduled status).
function soonestUpcomingAppointment(appointments: Appointment[]): Appointment | null {
  const now = new Date();
  const future = appointments
    .filter(a => a.status === 'scheduled' && new Date(a.scheduled_date) > now)
    .sort((a, b) => new Date(a.scheduled_date).getTime() - new Date(b.scheduled_date).getTime());
  return future[0] ?? null;
}

// Days until a date string.
function daysUntil(dateStr: string): number {
  const diff = new Date(dateStr).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

export function PostAvsActionPanel({ profileId, actionItems, upcomingAppointments, onDismiss }: Props) {
  const queryClient = useQueryClient();
  const nextAppt = soonestUpcomingAppointment(upcomingAppointments);
  const daysToAppt = nextAppt ? daysUntil(nextAppt.scheduled_date) : null;

  const followUpMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      actionItemsApi.updateFollowUp(profileId, id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['followUps', profileId] }),
  });

  const labMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      actionItemsApi.updateLabOrder(profileId, id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['labOrders', profileId] }),
  });

  const referralMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      actionItemsApi.updateReferral(profileId, id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['referrals', profileId] }),
  });

  const pendingFollowUps = actionItems.follow_ups.filter(f => f.status === 'pending');
  const pendingLabs = actionItems.lab_orders.filter(l => l.status === 'ordered');
  const pendingReferrals = actionItems.referrals.filter(r => r.status === 'pending');

  if (!pendingFollowUps.length && !pendingLabs.length && !pendingReferrals.length) return null;

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-amber-900">Action items from this visit</h3>
          <p className="text-sm text-amber-700 mt-0.5">Here's what was ordered — take action while it's fresh.</p>
        </div>
        <button onClick={onDismiss} className="text-amber-500 hover:text-amber-700 mt-0.5 flex-shrink-0">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Follow-ups */}
      {pendingFollowUps.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-amber-800">Follow-up appointments</h4>
          {pendingFollowUps.map(fu => (
            <div key={fu.id} className="flex items-start justify-between gap-3 bg-white rounded border border-amber-100 px-3 py-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-800">{fu.description}</p>
                {fu.timeframe && (
                  <p className={`text-xs mt-0.5 ${isUrgentFollowUp(fu) ? 'text-orange-600 font-medium' : 'text-gray-500'}`}>
                    {isUrgentFollowUp(fu) ? '⚡ ' : ''}{fu.timeframe}
                    {isUrgentFollowUp(fu) ? ' — book now' : ''}
                  </p>
                )}
              </div>
              <button
                onClick={() => followUpMutation.mutate({ id: fu.id, status: 'booked' })}
                disabled={followUpMutation.isPending}
                className="text-xs px-2.5 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50 flex-shrink-0"
              >
                Booked
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Lab orders */}
      {pendingLabs.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-amber-800">
            Lab tests ordered
            {daysToAppt !== null && daysToAppt <= 21 && (
              <span className="ml-2 font-normal normal-case text-orange-600">
                — get done before your appointment in {daysToAppt} days
              </span>
            )}
          </h4>
          {pendingLabs.map(lab => (
            <div key={lab.id} className="flex items-center justify-between gap-3 bg-white rounded border border-amber-100 px-3 py-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-800">{lab.test_name}</p>
                {lab.ordered_date && (
                  <p className="text-xs text-gray-500 mt-0.5">Ordered {lab.ordered_date}</p>
                )}
              </div>
              <button
                onClick={() => labMutation.mutate({ id: lab.id, status: 'completed' })}
                disabled={labMutation.isPending}
                className="text-xs px-2.5 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50 flex-shrink-0"
              >
                Done
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Referrals */}
      {pendingReferrals.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-amber-800">Referrals to schedule</h4>
          {pendingReferrals.map(ref => (
            <div key={ref.id} className="flex items-start justify-between gap-3 bg-white rounded border border-amber-100 px-3 py-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-800">{ref.specialty}{ref.provider_name ? ` — ${ref.provider_name}` : ''}</p>
                {ref.reason && <p className="text-xs text-gray-500 mt-0.5">{ref.reason}</p>}
              </div>
              <button
                onClick={() => referralMutation.mutate({ id: ref.id, status: 'scheduled' })}
                disabled={referralMutation.isPending}
                className="text-xs px-2.5 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50 flex-shrink-0"
              >
                Scheduled
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
