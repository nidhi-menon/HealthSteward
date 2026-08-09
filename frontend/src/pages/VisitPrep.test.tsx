import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';

import VisitPrep from './VisitPrep';
import { renderWithProviders } from '../test/render';
import { aDoctor, anAppointment } from '../test/fixtures';
import type { Appointment, HealthProfile, VisitPrep as VisitPrepType } from '../types';

vi.mock('../api/client', () => ({
  profiles: { get: vi.fn() },
  appointments: { get: vi.fn(), update: vi.fn(async () => ({})) },
  doctors: { list: vi.fn() },
  visitPrep: { get: vi.fn(), prepare: vi.fn(), update: vi.fn() },
}));

const { profiles, appointments, doctors, visitPrep } = await import('../api/client');

const PROFILE: HealthProfile = {
  id: 'profile-1',
  name: 'Alex Rivera',
  date_of_birth: '1986-04-02',
  blood_type: null,
  allergies: null,
  emergency_contact_name: null,
  emergency_contact_phone: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const PREP: VisitPrepType = {
  id: 'prep-1',
  appointment_id: 'appointment-1',
  generated_questions: {
    'Condition Management': ['How is my A1C trending?', 'Should the dose change?'],
  },
  context_summary: 'Type 2 diabetes, stable on metformin.',
  used_fallback: false,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

function renderPrep({
  prep = PREP as VisitPrepType | null,
  appointment = anAppointment(),
}: { prep?: VisitPrepType | null; appointment?: Appointment } = {}) {
  vi.mocked(profiles.get).mockResolvedValue(PROFILE);
  vi.mocked(appointments.get).mockResolvedValue(appointment);
  vi.mocked(doctors.list).mockResolvedValue([aDoctor()]);
  vi.mocked(visitPrep.get).mockImplementation(
    prep ? async () => prep : async () => { throw new Error('no prep yet'); },
  );

  return renderWithProviders(
    <Routes>
      <Route
        path="/profiles/:profileId/appointments/:appointmentId/prep"
        element={<VisitPrep />}
      />
    </Routes>,
    { route: '/profiles/profile-1/appointments/appointment-1/prep' },
  );
}

/**
 * Print / Save as PDF (issue #99, DEC-037).
 *
 * jsdom has no layout engine and never applies `@media print`, so these can't
 * assert what the printed page looks like. What they can pin is the contract
 * the print stylesheet is written against: which elements are marked
 * `print-hide` (controls and chrome) and `print-only` (text that exists solely
 * to identify a sheet off-screen). If someone adds a button without the class,
 * or renames the class, that's what breaks here — the rest is a manual check,
 * recorded in the PR's test plan.
 */
describe('VisitPrep print / save as PDF', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // `window.print` is not implemented in jsdom — assigning is how it gets
    // observed at all, and re-armed per test since clearAllMocks keeps
    // implementations but a stale spy would leak call counts.
    window.print = vi.fn();
  });

  it('offers Print / Save as PDF once prep exists', async () => {
    renderPrep();

    expect(
      await screen.findByRole('button', { name: /print \/ save as pdf/i }),
    ).toBeInTheDocument();
  });

  it('does not offer it before anything has been generated', async () => {
    renderPrep({ prep: null });

    // Wait for the page to settle on the pre-generation state.
    expect(
      await screen.findByRole('button', { name: /generate questions with ai/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /print \/ save as pdf/i }),
    ).not.toBeInTheDocument();
  });

  it('opens the browser print dialog, which is also how Save as PDF happens', async () => {
    renderPrep();
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole('button', { name: /print \/ save as pdf/i }),
    );

    // No new dependency, no server round-trip, nothing leaving the machine:
    // the browser's own dialog is the PDF export (DEC-037).
    await waitFor(() => expect(window.print).toHaveBeenCalledTimes(1));
  });

  it('names the patient and print date only on the printed sheet', async () => {
    renderPrep();

    // On screen the surrounding app says whose record this is; on paper
    // nothing does, so this line is print-only rather than always shown.
    const identity = await screen.findByText(/Alex Rivera — printed from HealthSteward/);
    expect(identity).toHaveClass('print-only');
  });

  it('marks the app chrome and controls as print-hidden', async () => {
    renderPrep();

    const printButton = await screen.findByRole('button', {
      name: /print \/ save as pdf/i,
    });
    // The print control must not print itself.
    expect(printButton).toHaveClass('print-hide');

    // Editing affordances are screen-only too.
    expect(screen.getByRole('button', { name: /^edit$/i })).toHaveClass('print-hide');
    // Regenerate sits in a print-hidden row, so the row doesn't leave a gap.
    expect(
      screen.getByRole('button', { name: /regenerate questions/i })
        .closest('.print-hide'),
    ).not.toBeNull();
  });

  it('keeps the questions and summary themselves printable', async () => {
    renderPrep();

    // The content is the point of the sheet — nothing here is print-hidden.
    const question = await screen.findByText('How is my A1C trending?');
    expect(question.closest('.print-hide')).toBeNull();
    expect(
      screen.getByText('Type 2 diabetes, stable on metformin.').closest('.print-hide'),
    ).toBeNull();
  });
});
