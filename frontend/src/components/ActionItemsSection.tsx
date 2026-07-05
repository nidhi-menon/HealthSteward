import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { actionItems as actionItemsApi } from '../api/client';
import { Card, CardHeader, CardContent } from './Card';
import { useNavigate } from 'react-router-dom';
import type { Appointment, Doctor } from '../types';

interface Props {
  profileId: string;
  appointments: Appointment[];
  doctors: Doctor[];
}

function daysUntil(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
}

function soonestUpcomingAppointment(appointments: Appointment[]): Appointment | null {
  const now = new Date();
  const future = appointments
    .filter(a => a.status === 'scheduled' && new Date(a.scheduled_date) > now)
    .sort((a, b) => new Date(a.scheduled_date).getTime() - new Date(b.scheduled_date).getTime());
  return future[0] ?? null;
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

  const total = followUps.length + labOrders.length + referrals.length + unpreparedAppointments.length;
  if (total === 0) return null;

  const nextAppt = soonestUpcomingAppointment(appointments);
  const daysToAppt = nextAppt ? daysUntil(nextAppt.scheduled_date) : null;

  return (
    <Card className="border-orange-200 bg-orange-50">
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-orange-500 text-white text-xs font-bold">{total}</span>
          <h3 className="font-semibold text-orange-900">Needs Attention</h3>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">

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

        {followUps.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Follow-up appointments</p>
            {followUps.map(fu => (
              <div key={fu.id} className="flex items-start justify-between gap-3 bg-white rounded border border-orange-100 px-3 py-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800">{fu.description}</p>
                  {fu.timeframe && <p className="text-xs text-gray-500 mt-0.5">{fu.timeframe}</p>}
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
            {labOrders.map(lab => (
              <div key={lab.id} className="flex items-center justify-between gap-3 bg-white rounded border border-orange-100 px-3 py-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800">{lab.test_name}</p>
                  {lab.ordered_date && <p className="text-xs text-gray-500 mt-0.5">Ordered {lab.ordered_date}</p>}
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

        {referrals.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Referrals to schedule</p>
            {referrals.map(ref => (
              <div key={ref.id} className="flex items-start justify-between gap-3 bg-white rounded border border-orange-100 px-3 py-2">
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

      </CardContent>
    </Card>
  );
}
