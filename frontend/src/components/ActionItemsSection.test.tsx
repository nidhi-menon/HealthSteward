import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ActionItemsSection } from './ActionItemsSection';
import { renderWithProviders } from '../test/render';
import { aDoctor, anAppointment, aFollowUp, aSnoozedItem } from '../test/fixtures';

// Stubbed at the client boundary so nothing needs a server. Every list
// defaults to empty; a test overrides only the one it is about.
vi.mock('../api/client', () => ({
  actionItems: {
    listFollowUps: vi.fn(async () => []),
    listLabOrders: vi.fn(async () => []),
    listReferrals: vi.fn(async () => []),
    listSnoozedItems: vi.fn(async () => []),
    pastDueAppointments: vi.fn(async () => []),
    upcomingWithoutPrep: vi.fn(async () => []),
    vitalsAlerts: vi.fn(async () => []),
    completedWithoutAvs: vi.fn(async () => []),
    updateFollowUp: vi.fn(async () => ({})),
    updateLabOrder: vi.fn(async () => ({})),
    updateReferral: vi.fn(async () => ({})),
    snoozeNudge: vi.fn(async () => ({})),
  },
}));

const { actionItems } = await import('../api/client');
const api = vi.mocked(actionItems, true);

// Every date-relative assertion below is measured from here rather than from
// the real clock, which is the whole point of testing nudge logic.
const NOW = new Date('2026-06-10T12:00:00Z');

function renderSection(props: Partial<Parameters<typeof ActionItemsSection>[0]> = {}) {
  return renderWithProviders(
    <ActionItemsSection
      profileId="profile-1"
      appointments={props.appointments ?? []}
      doctors={props.doctors ?? [aDoctor()]}
    />,
  );
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(NOW);

  // Re-arm every list to empty. `clearAllMocks` only clears recorded calls —
  // an implementation set by `mockResolvedValue` in one test survives into the
  // next one, which silently renders an extra section and breaks unrelated
  // queries. Setting them explicitly is what makes each test independent.
  vi.clearAllMocks();
  api.listFollowUps.mockResolvedValue([]);
  api.listLabOrders.mockResolvedValue([]);
  api.listReferrals.mockResolvedValue([]);
  api.listSnoozedItems.mockResolvedValue([]);
  api.pastDueAppointments.mockResolvedValue([]);
  api.upcomingWithoutPrep.mockResolvedValue([]);
  api.vitalsAlerts.mockResolvedValue([]);
  api.completedWithoutAvs.mockResolvedValue([]);
});

describe('ActionItemsSection', () => {
  it('renders nothing at all when there is nothing to act on', async () => {
    const { container } = renderSection();

    await waitFor(() => expect(api.listFollowUps).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('counts everything outstanding in one badge', async () => {
    api.listFollowUps.mockResolvedValue([
      aFollowUp({ id: 'fu-1' }),
      aFollowUp({ id: 'fu-2', description: 'Book cardiology' }),
    ]);
    api.upcomingWithoutPrep.mockResolvedValue([
      anAppointment({ scheduled_date: '2026-06-13T10:00:00Z' }),
    ]);

    renderSection();

    expect(await screen.findByText('Needs Attention')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('counts down the days to an unprepared appointment', async () => {
    api.upcomingWithoutPrep.mockResolvedValue([
      anAppointment({ scheduled_date: '2026-06-13T12:00:00Z' }),
    ]);

    renderSection();

    // 2026-06-13 is 3 days after the frozen NOW.
    expect(await screen.findByText(/in 3 days — no prep generated yet/)).toBeInTheDocument();
  });

  it('singularises the countdown when an appointment is one day out', async () => {
    api.upcomingWithoutPrep.mockResolvedValue([
      anAppointment({ scheduled_date: '2026-06-11T12:00:00Z' }),
    ]);

    renderSection();

    expect(await screen.findByText(/in 1 day — no prep/)).toBeInTheDocument();
  });

  describe('follow-up urgency, computed from elapsed fraction of the timeframe', () => {
    it('says nothing extra while a follow-up is still comfortably in its window', async () => {
      // Created 10 days ago against a 3-month window: ~11% elapsed.
      api.listFollowUps.mockResolvedValue([
        aFollowUp({ created_at: '2026-05-31T12:00:00Z', timeframe: '3 months' }),
      ]);

      renderSection();

      expect(await screen.findByText('3 months')).toBeInTheDocument();
      expect(screen.queryByText(/Overdue/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Approaching deadline/)).not.toBeInTheDocument();
    });

    it('warns once three quarters of the window has gone', async () => {
      // 70 days elapsed against 90: 78%.
      api.listFollowUps.mockResolvedValue([
        aFollowUp({ created_at: '2026-04-01T12:00:00Z', timeframe: '3 months' }),
      ]);

      renderSection();

      expect(await screen.findByText(/Approaching deadline/)).toBeInTheDocument();
      expect(screen.queryByText(/Overdue/)).not.toBeInTheDocument();
    });

    it('marks it overdue once the window has fully elapsed', async () => {
      // 100 days elapsed against 90.
      api.listFollowUps.mockResolvedValue([
        aFollowUp({ created_at: '2026-03-02T12:00:00Z', timeframe: '3 months' }),
      ]);

      renderSection();

      expect(await screen.findByText(/Overdue/)).toBeInTheDocument();
    });

    it('stays silent when the timeframe is not a duration it can parse', async () => {
      api.listFollowUps.mockResolvedValue([
        aFollowUp({ created_at: '2020-01-01T00:00:00Z', timeframe: 'as needed' }),
      ]);

      renderSection();

      expect(await screen.findByText('as needed')).toBeInTheDocument();
      expect(screen.queryByText(/Overdue/)).not.toBeInTheDocument();
    });
  });

  describe('snoozing', () => {
    it('sends the chosen duration as an absolute date', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      api.listFollowUps.mockResolvedValue([aFollowUp()]);

      renderSection();
      await user.click(await screen.findByRole('button', { name: '2w' }));

      await waitFor(() => expect(api.updateFollowUp).toHaveBeenCalled());
      const [, id, body] = api.updateFollowUp.mock.calls[0];
      expect(id).toBe('follow-up-1');

      // 14 days after the frozen clock, not 7 and not 30.
      const snoozedUntil = new Date(body.snoozed_until as string);
      const daysOut = Math.round(
        (snoozedUntil.getTime() - NOW.getTime()) / (1000 * 60 * 60 * 24),
      );
      expect(daysOut).toBe(14);
    });

    it('offers an undo, and un-snoozing clears the date rather than resetting it', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      api.listFollowUps.mockResolvedValue([aFollowUp()]);

      renderSection();
      await user.click(await screen.findByRole('button', { name: '1w' }));

      expect(await screen.findByText('Snoozed "Recheck blood pressure"')).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Undo' }));

      await waitFor(() => expect(api.updateFollowUp).toHaveBeenCalledTimes(2));
      expect(api.updateFollowUp.mock.calls[1][2]).toEqual({ snoozed_until: null });
    });

    it('drops the undo banner once its window passes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      api.listFollowUps.mockResolvedValue([aFollowUp()]);

      renderSection();
      await user.click(await screen.findByRole('button', { name: '1w' }));
      expect(await screen.findByText(/^Snoozed /)).toBeInTheDocument();

      vi.advanceTimersByTime(9000);

      await waitFor(() =>
        expect(screen.queryByText(/^Snoozed /)).not.toBeInTheDocument(),
      );
    });

    it('replaces the banner on a second snooze instead of stacking two', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      api.listFollowUps.mockResolvedValue([
        aFollowUp({ id: 'fu-1', description: 'First item' }),
        aFollowUp({ id: 'fu-2', description: 'Second item' }),
      ]);

      renderSection();
      const snoozeButtons = await screen.findAllByRole('button', { name: '1w' });
      await user.click(snoozeButtons[0]);
      await user.click(snoozeButtons[1]);

      await waitFor(() =>
        expect(screen.getByText('Snoozed "Second item"')).toBeInTheDocument(),
      );
      expect(screen.queryByText('Snoozed "First item"')).not.toBeInTheDocument();
    });
  });

  it('only fetches snoozed items once the section is opened', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    api.listFollowUps.mockResolvedValue([aFollowUp()]);
    api.listSnoozedItems.mockResolvedValue([
      aSnoozedItem({ label: 'Fasting glucose', category: 'lab_order', item_id: 'lab-1' }),
    ]);

    renderSection();
    await screen.findByText('Needs Attention');
    expect(api.listSnoozedItems).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Show snoozed' }));

    expect(await screen.findByText('Fasting glucose')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Un-snooze now' }));

    await waitFor(() => expect(api.updateLabOrder).toHaveBeenCalled());
    expect(api.updateLabOrder.mock.calls[0][2]).toEqual({ snoozed_until: null });
  });

  it('marks a follow-up booked without touching its snooze', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    api.listFollowUps.mockResolvedValue([aFollowUp()]);

    renderSection();
    await user.click(await screen.findByRole('button', { name: 'Booked' }));

    await waitFor(() => expect(api.updateFollowUp).toHaveBeenCalled());
    expect(api.updateFollowUp.mock.calls[0][2]).toEqual({ status: 'booked' });
  });
});
