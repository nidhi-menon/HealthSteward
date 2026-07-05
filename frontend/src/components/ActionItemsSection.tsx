import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { actionItems as actionItemsApi } from '../api/client';
import { Card, CardHeader, CardContent } from './Card';

interface Props {
  profileId: string;
}

export function ActionItemsSection({ profileId }: Props) {
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

  const total = followUps.length + labOrders.length + referrals.length;
  if (total === 0) return null;

  return (
    <Card className="border-orange-200 bg-orange-50">
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-orange-500 text-white text-xs font-bold">{total}</span>
          <h3 className="font-semibold text-orange-900">Needs Attention</h3>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">

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
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-800">Lab tests ordered</p>
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
