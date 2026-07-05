import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { actionItems as actionItemsApi } from '../api/client';
import { Card, CardHeader, CardContent } from './Card';
import type { Appointment, Doctor } from '../types';

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

// Parse free-text timeframe to days, returns null if unparseable
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

// Returns how overdue a follow-up is as a fraction of its timeframe (>1 = overdue)
function followUpOverdueFraction(createdAt: string, timeframe: string | null): number | null {
  if (!timeframe) return null;
  const days = timeframeToDays(timeframe);
  if (!days) return null;
  return daysSince(createdAt) / days;
}

export function ActionItemsSection({ profileId, appointments, doctors }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: followUps = [] } = useQuery({
    queryKey: ['followUps', profileId],
    queryFn: () => actionItemsApi.listFollowUps(profileId, 'pending'),
    enabled: !!profileId,
  });

  const { data: labOrders = [] } = useQuery({
    queryKey: ['labOrders', profileId],
    queryFn: () => actionItemsApi.listLabOrders(profileId, 'ordered'),
    enabled: !!profileId,
  });

  const { data: referrals = [] } = useQuery({
    queryKey: ['referrals', profileId],
    queryFn: () => actionItemsApi.listReferrals(profileId, 'pending'),
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

  // Past-due: scheduled appointments whose date has already passed
  const now = new Date();
  const pastDueAppointments = appointments.filter(
    a => a.status === 'scheduled' && new Date(a.scheduled_date) < now
  );

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

  const total =
    unpreparedAppointments.length +
    followUps.length +
    labOrders.length +
    referrals.length +
    vitalsAlerts.length +
    completedWithoutAvs.length +
    pastDueAppointments.length;

  if (total === 0) return null;

  const nextAppt = soonestUpcomingAppointment(appointments);
  const daysToAppt = nextAppt ? daysUntil(nextAppt.scheduled_date) : null;

  return (
    <Card className="border-orange-200 bg-orange-50">
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-orange-500 text-white text-xs font-bold">
            {total}
          </span>
          <h3 className="font-semibold text-orange-900">Needs Attention</h3>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">

        {/* Visit prep nudge */}
        {unpreparedAppointments.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Visit prep needed</p>
            {unpreparedAppointments.map(appt => {
              const doctor = doctors.find(d => d.id === appt.doctor_id);
              const label = doctor ? doctor.name : appt.purpose || 'Appointment';
              const days = daysUntil(appt.scheduled_date);
              return (
                <div key={appt.id} className="flex items-center justify-between gap-3 bg-white rounded border border-orange-100 px-3 py-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{label}</p>
                    <p className="text-xs text-orange-600 font-medium mt-0.5">
                      in {days} day{days !== 1 ? 's' : ''} — no prep generated yet
                    </p>
                  </div>
                  <button
                    onClick={() => navigate(`/profiles/${profileId}/appointments/${appt.id}/prep`)}
                    className="text-xs px-2.5 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700 flex-shrink-0"
                  >
                    Prepare
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Past-due appointments not marked complete */}
        {pastDueAppointments.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Appointments to close out</p>
            {pastDueAppointments.map(appt => {
              const doctor = doctors.find(d => d.id === appt.doctor_id);
              const label = doctor ? doctor.name : appt.purpose || 'Appointment';
              const ago = daysSince(appt.scheduled_date);
              return (
                <div key={appt.id} className="flex items-center justify-between gap-3 bg-white rounded border border-orange-100 px-3 py-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{label}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {ago} day{ago !== 1 ? 's' : ''} ago — not marked complete, no visit notes
                    </p>
                  </div>
                  <button
                    onClick={() => navigate(`/profiles/${profileId}/appointments/${appt.id}/prep`)}
                    className="text-xs px-2.5 py-1 bg-gray-600 text-white rounded hover:bg-gray-700 flex-shrink-0"
                  >
                    Add notes
                  </button>
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
                <div key={appt.id} className="flex items-start gap-3 bg-white rounded border border-orange-100 px-3 py-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{label}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {new Date(appt.scheduled_date).toLocaleDateString()} — no AVS parsed for this visit
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">Drop the PDF in <code className="bg-gray-100 px-1 rounded">data/avs/</code> to update your profile</p>
                  </div>
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
              <div key={i} className="flex items-start gap-3 bg-white rounded border border-orange-100 px-3 py-2">
                <span className="text-base flex-shrink-0 mt-0.5">
                  {alert.direction === 'up' ? '↑' : '↓'}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800">{alert.message}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {alert.oldest_value} → {alert.newest_value} over {alert.visit_count} visits — bring this up at your next appointment
                  </p>
                </div>
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
                <div key={fu.id} className={`flex items-start justify-between gap-3 bg-white rounded border px-3 py-2 ${isOverdue ? 'border-red-200' : isStale ? 'border-orange-200' : 'border-orange-100'}`}>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{fu.description}</p>
                    {fu.timeframe && (
                      <p className={`text-xs mt-0.5 ${isOverdue ? 'text-red-600 font-medium' : isStale ? 'text-orange-600' : 'text-gray-500'}`}>
                        {isOverdue ? 'Overdue — ' : isStale ? 'Approaching deadline — ' : ''}{fu.timeframe}
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
              );
            })}
          </div>
        )}

        {/* Lab orders with appointment-proximity warning */}
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
                <div key={lab.id} className={`flex items-center justify-between gap-3 bg-white rounded border px-3 py-2 ${isStale ? 'border-orange-200' : 'border-orange-100'}`}>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{lab.test_name}</p>
                    <p className={`text-xs mt-0.5 ${isStale ? 'text-orange-600' : 'text-gray-500'}`}>
                      {isStale ? `Ordered ${age} days ago — results take ~1 week` : lab.ordered_date ? `Ordered ${lab.ordered_date}` : null}
                    </p>
                  </div>
                  <button
                    onClick={() => labMutation.mutate({ id: lab.id, status: 'completed' })}
                    disabled={labMutation.isPending}
                    className="text-xs px-2.5 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50 flex-shrink-0"
                  >
                    Done
                  </button>
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
                <div key={ref.id} className={`flex items-start justify-between gap-3 bg-white rounded border px-3 py-2 ${isStale ? 'border-orange-200' : 'border-orange-100'}`}>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{ref.specialty}{ref.provider_name ? ` — ${ref.provider_name}` : ''}</p>
                    {ref.reason && <p className="text-xs text-gray-500 mt-0.5">{ref.reason}</p>}
                    {isStale && (
                      <p className="text-xs text-orange-600 mt-0.5">Pending for {age} days</p>
                    )}
                  </div>
                  <button
                    onClick={() => referralMutation.mutate({ id: ref.id, status: 'scheduled' })}
                    disabled={referralMutation.isPending}
                    className="text-xs px-2.5 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50 flex-shrink-0"
                  >
                    Scheduled
                  </button>
                </div>
              );
            })}
          </div>
        )}

      </CardContent>
    </Card>
  );
}
