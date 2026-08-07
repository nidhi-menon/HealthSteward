import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ParsedItemsReview } from './ParsedItemsReview';
import { renderWithProviders } from '../test/render';
import type { ApplyItemsRequest, ApplyPlan, ParsedItemsResponse } from '../types';

function parsedItems(overrides: Partial<ParsedItemsResponse> = {}): ParsedItemsResponse {
  return {
    patient: { name: 'John Doe', visit_date: '06/01/2026' },
    provider: { name: 'Dr. Ada Reyes' },
    vitals: {
      weight: null, bmi: null, blood_pressure: null,
      heart_rate: null, temperature: null,
    },
    diagnoses: [],
    medication_changes: [],
    lab_orders: [],
    referrals: [],
    follow_up_recommended: [],
    upcoming_appointments: [],
    notes: [],
    ...overrides,
  };
}

/** A minimal plan that satisfies the confirm modal without asserting on its diff rendering. */
function stubPlan(overrides: Partial<ApplyPlan> = {}): ApplyPlan {
  return {
    plan_fingerprint: 'fp-1',
    entries: [],
    counts: {},
    skipped: {},
    ...overrides,
  };
}

function renderReview(data: ParsedItemsResponse) {
  const onApply = vi.fn();
  const onBack = vi.fn();
  const onPreview = vi.fn().mockResolvedValue(stubPlan());
  const result = renderWithProviders(
    <ParsedItemsReview
      data={data}
      onApply={onApply}
      onPreview={onPreview}
      onBack={onBack}
      isApplying={false}
    />,
  );
  return { ...result, onApply, onBack, onPreview };
}

/** Walk the confirm modal and return the request the component would send. */
async function confirmAndCapture(
  user: ReturnType<typeof userEvent.setup>,
  onApply: ReturnType<typeof vi.fn>,
): Promise<ApplyItemsRequest> {
  await user.click(screen.getByRole('button', { name: /Review Changes/ }));
  await user.click(await screen.findByRole('button', { name: /Yes, Update Profile/ }));
  expect(onApply).toHaveBeenCalledTimes(1);
  return onApply.mock.calls[0][0] as ApplyItemsRequest;
}

describe('ParsedItemsReview', () => {
  it('splits medication changes into starts, stops and updates by action', async () => {
    const user = userEvent.setup();
    const { onApply } = renderReview(parsedItems({
      medication_changes: [
        { name: 'Lisinopril', action: 'start', strength: '10mg', instructions: null, date: null },
        { name: 'Ibuprofen', action: 'stop', strength: null, instructions: null, date: null },
        { name: 'Metformin', action: 'changed', strength: '850mg', instructions: null, date: null },
      ],
    }));

    const request = await confirmAndCapture(user, onApply);

    expect(request.medication_starts.map(m => m.name)).toEqual(['Lisinopril']);
    expect(request.medication_stops.map(m => m.name)).toEqual(['Ibuprofen']);
    expect(request.medication_updates.map(m => m.name)).toEqual(['Metformin']);
  });

  it('carries every accepted category through to the apply request', async () => {
    const user = userEvent.setup();
    const { onApply } = renderReview(parsedItems({
      diagnoses: [{
        condition: 'Hypertension', icd_10: 'I10',
        severity: 'moderate', diagnosed_date: null, status: 'active',
      }],
      lab_orders: [{ test: 'Lipid panel', ordered_date: '06/01/2026' }],
      referrals: [{ specialty: 'Cardiology', provider: null, reason: null }],
      follow_up_recommended: [{
        description: 'Recheck BP', timeframe: '3 months', target_date: null,
      }],
      upcoming_appointments: [{
        description: 'Cardiology follow-up', date: '09/01/2026',
        time: null, location: null, phone: null,
      }],
    }));

    const request = await confirmAndCapture(user, onApply);

    expect(request.diagnoses).toHaveLength(1);
    expect(request.lab_orders[0].test).toBe('Lipid panel');
    expect(request.referrals[0].specialty).toBe('Cardiology');
    expect(request.follow_ups[0].description).toBe('Recheck BP');
    expect(request.appointments[0].date).toBe('09/01/2026');
  });

  describe('selective apply', () => {
    it('leaves out an item the user removed', async () => {
      const user = userEvent.setup();
      const { onApply } = renderReview(parsedItems({
        diagnoses: [
          { condition: 'Hypertension', icd_10: null, severity: null, diagnosed_date: null, status: null },
          { condition: 'Misread condition', icd_10: null, severity: null, diagnosed_date: null, status: null },
        ],
      }));

      // The remove control sits next to the item, so scope the lookup rather
      // than relying on the order of every "Remove item" button on the page.
      const misread = screen.getByText('Misread condition').closest('div.group');
      await user.click(within(misread as HTMLElement).getByTitle('Remove item'));

      const request = await confirmAndCapture(user, onApply);

      expect(request.diagnoses.map(d => d.condition)).toEqual(['Hypertension']);
    });

    it('sends nothing at all if every item is removed, and blocks the apply', async () => {
      const user = userEvent.setup();
      renderReview(parsedItems({
        diagnoses: [{
          condition: 'Hypertension', icd_10: null, severity: null,
          diagnosed_date: null, status: null,
        }],
      }));

      expect(screen.getByRole('button', { name: /Review Changes/ })).toBeEnabled();

      const row = screen.getByText('Hypertension').closest('div.group');
      await user.click(within(row as HTMLElement).getByTitle('Remove item'));

      expect(screen.getByText(/^0 items to apply/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Review Changes/ })).toBeDisabled();
    });
  });

  it('sends the corrected value when the user fixes a misparse', async () => {
    const user = userEvent.setup();
    const { onApply } = renderReview(parsedItems({
      diagnoses: [{
        condition: 'Hypertenshun', icd_10: null, severity: null,
        diagnosed_date: null, status: null,
      }],
    }));

    await user.click(screen.getByText('Hypertenshun'));
    const input = screen.getByDisplayValue('Hypertenshun');
    await user.clear(input);
    await user.type(input, 'Hypertension');
    await user.keyboard('{Enter}');

    expect(screen.getByText(/1 edit made/)).toBeInTheDocument();

    const request = await confirmAndCapture(user, onApply);
    expect(request.diagnoses[0].condition).toBe('Hypertension');
  });

  it('sends vitals only when the visit actually recorded some', async () => {
    const user = userEvent.setup();
    const { onApply } = renderReview(parsedItems({
      vitals: {
        weight: '180 lb', bmi: null, blood_pressure: '128/82',
        heart_rate: null, temperature: null,
      },
    }));

    const request = await confirmAndCapture(user, onApply);
    expect(request.vitals?.blood_pressure).toBe('128/82');
  });

  it('shows notes for review but never applies them', async () => {
    const user = userEvent.setup();
    const { onApply } = renderReview(parsedItems({
      notes: ['Drink more water'],
      diagnoses: [{
        condition: 'Hypertension', icd_10: null, severity: null,
        diagnosed_date: null, status: null,
      }],
    }));

    expect(screen.getByText('Drink more water')).toBeInTheDocument();

    const request = await confirmAndCapture(user, onApply);
    expect(Object.values(request).flat()).not.toContain('Drink more water');
  });

  it('does not apply anything until the confirmation is accepted', async () => {
    const user = userEvent.setup();
    const { onApply } = renderReview(parsedItems({
      diagnoses: [{
        condition: 'Hypertension', icd_10: null, severity: null,
        diagnosed_date: null, status: null,
      }],
    }));

    await user.click(screen.getByRole('button', { name: /Review Changes/ }));
    expect(onApply).not.toHaveBeenCalled();

    await user.click(await screen.findByRole('button', { name: 'Go Back' }));
    expect(onApply).not.toHaveBeenCalled();
  });
});
