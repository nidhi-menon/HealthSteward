import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { PostAvsActionPanel } from './PostAvsActionPanel';
import { renderWithProviders } from '../test/render';
import { anAppointment, aFollowUp, aLabOrder, aReferral } from '../test/fixtures';
import type { ActionItems } from '../types';

vi.mock('../api/client', () => ({
  actionItems: {
    updateFollowUp: vi.fn(async () => ({})),
    updateLabOrder: vi.fn(async () => ({})),
    updateReferral: vi.fn(async () => ({})),
  },
}));

const { actionItems } = await import('../api/client');
const api = vi.mocked(actionItems, true);

const NOW = new Date('2026-06-10T12:00:00Z');

function renderPanel({
  actionItems: items = {},
  upcomingAppointments = [],
}: {
  actionItems?: Partial<ActionItems>;
  upcomingAppointments?: ReturnType<typeof anAppointment>[];
} = {}) {
  const onDismiss = vi.fn();
  const result = renderWithProviders(
    <PostAvsActionPanel
      profileId="profile-1"
      actionItems={{
        follow_ups: items.follow_ups ?? [],
        lab_orders: items.lab_orders ?? [],
        referrals: items.referrals ?? [],
      }}
      upcomingAppointments={upcomingAppointments}
      onDismiss={onDismiss}
    />,
  );
  return { ...result, onDismiss };
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(NOW);
  vi.clearAllMocks();
});

describe('PostAvsActionPanel', () => {
  it('stays hidden when every item from the visit is already resolved', () => {
    const { container } = renderPanel({
      actionItems: {
        follow_ups: [aFollowUp({ status: 'booked' })],
        lab_orders: [aLabOrder({ status: 'completed' })],
        referrals: [aReferral({ status: 'completed' })],
      },
    });

    expect(container).toBeEmptyDOMElement();
  });

  it('shows only the items still outstanding', () => {
    renderPanel({
      actionItems: {
        follow_ups: [
          aFollowUp({ id: 'fu-1', description: 'Recheck blood pressure' }),
          aFollowUp({ id: 'fu-2', description: 'Already booked', status: 'booked' }),
        ],
      },
    });

    expect(screen.getByText('Recheck blood pressure')).toBeInTheDocument();
    expect(screen.queryByText('Already booked')).not.toBeInTheDocument();
  });

  describe('follow-up urgency', () => {
    it('flags a near-term follow-up as book-now', () => {
      renderPanel({
        actionItems: { follow_ups: [aFollowUp({ timeframe: '3 months' })] },
      });

      expect(screen.getByText(/book now/)).toBeInTheDocument();
      expect(screen.getByText(/⚡/)).toBeInTheDocument();
    });

    it('leaves a distant follow-up unflagged', () => {
      // 1 year > the 180-day urgency threshold.
      renderPanel({
        actionItems: { follow_ups: [aFollowUp({ timeframe: '1 year' })] },
      });

      expect(screen.getByText('1 year')).toBeInTheDocument();
      expect(screen.queryByText(/book now/)).not.toBeInTheDocument();
    });

    it('leaves an unparseable timeframe unflagged rather than guessing', () => {
      renderPanel({
        actionItems: { follow_ups: [aFollowUp({ timeframe: 'when convenient' })] },
      });

      expect(screen.getByText('when convenient')).toBeInTheDocument();
      expect(screen.queryByText(/book now/)).not.toBeInTheDocument();
    });
  });

  describe('lab-before-appointment warning', () => {
    it('warns when the next appointment is close enough for labs to matter', () => {
      renderPanel({
        actionItems: { lab_orders: [aLabOrder()] },
        upcomingAppointments: [
          anAppointment({ scheduled_date: '2026-06-24T12:00:00Z' }),
        ],
      });

      expect(
        screen.getByText(/get done before your appointment in 14 days/),
      ).toBeInTheDocument();
    });

    it('stays quiet when the next appointment is further out than the window', () => {
      renderPanel({
        actionItems: { lab_orders: [aLabOrder()] },
        upcomingAppointments: [
          anAppointment({ scheduled_date: '2026-07-30T12:00:00Z' }),
        ],
      });

      expect(screen.queryByText(/get done before your appointment/)).not.toBeInTheDocument();
    });

    it('ignores appointments in the past when picking the next one', () => {
      renderPanel({
        actionItems: { lab_orders: [aLabOrder()] },
        upcomingAppointments: [
          anAppointment({ id: 'past', scheduled_date: '2026-06-01T12:00:00Z' }),
          anAppointment({ id: 'future', scheduled_date: '2026-06-17T12:00:00Z' }),
        ],
      });

      expect(
        screen.getByText(/get done before your appointment in 7 days/),
      ).toBeInTheDocument();
    });
  });

  it('marks a follow-up booked', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPanel({ actionItems: { follow_ups: [aFollowUp()] } });

    await user.click(screen.getByRole('button', { name: 'Booked' }));

    await waitFor(() => expect(api.updateFollowUp).toHaveBeenCalled());
    expect(api.updateFollowUp.mock.calls[0][2]).toEqual({ status: 'booked' });
  });

  it('snoozes with an absolute date derived from the chosen duration', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPanel({ actionItems: { referrals: [aReferral()] } });

    await user.click(screen.getByRole('button', { name: '1m' }));

    await waitFor(() => expect(api.updateReferral).toHaveBeenCalled());
    const body = api.updateReferral.mock.calls[0][2];
    const daysOut = Math.round(
      (new Date(body.snoozed_until as string).getTime() - NOW.getTime()) /
        (1000 * 60 * 60 * 24),
    );
    expect(daysOut).toBe(30);
  });

  it('can be dismissed', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { onDismiss } = renderPanel({
      actionItems: { follow_ups: [aFollowUp()] },
    });

    const [dismiss] = screen.getAllByRole('button', { name: '' });
    await user.click(dismiss);

    expect(onDismiss).toHaveBeenCalled();
  });
});
