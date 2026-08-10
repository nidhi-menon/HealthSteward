import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';

import VisitPrepPage from './VisitPrep';
import { renderWithProviders } from '../test/render';
import { aDoctor, anAppointment } from '../test/fixtures';
import type { VisitPrep, VisitPrepVersion } from '../types';

/**
 * Issue #54: the read-only "Previous versions" disclosure.
 *
 * Scoped to that one affordance rather than the whole page — the durability
 * guarantee itself is covered by the backend suite, and what's worth pinning
 * here is that history stays hidden when there is none (so a prep that was
 * never regenerated looks exactly as it did before) and that expanding it
 * shows the old questions without offering any way to write over the current
 * ones.
 */

vi.mock('../api/client', () => ({
  profiles: { get: vi.fn() },
  appointments: { get: vi.fn(), checklist: vi.fn(), update: vi.fn() },
  doctors: { list: vi.fn() },
  visitPrep: { get: vi.fn(), prepare: vi.fn(), update: vi.fn(), versions: vi.fn() },
}));

const { profiles, appointments, doctors, visitPrep } = await import('../api/client');

function aPrep(overrides: Partial<VisitPrep> = {}): VisitPrep {
  return {
    id: 'prep-1',
    appointment_id: 'appointment-1',
    generated_questions: { 'Medication Review': ['Current question'] },
    context_summary: 'Current summary',
    used_fallback: false,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-02T00:00:00Z',
    ...overrides,
  };
}

function aVersion(overrides: Partial<VisitPrepVersion> = {}): VisitPrepVersion {
  return {
    id: 'version-1',
    visit_prep_id: 'prep-1',
    version_number: 1,
    generated_questions: { 'Medication Review': ['An older question'] },
    context_summary: 'Older summary',
    used_fallback: false,
    content_updated_at: '2026-06-01T00:00:00Z',
    created_at: '2026-06-02T00:00:00Z',
    ...overrides,
  };
}

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route
        path="/profiles/:profileId/appointments/:appointmentId/prep"
        element={<VisitPrepPage />}
      />
    </Routes>,
    { route: '/profiles/profile-1/appointments/appointment-1/prep' },
  );
}

beforeEach(() => {
  // Re-armed explicitly every test: vi.clearAllMocks() clears recorded calls
  // but not implementations, so a resolved value would leak forward (see the
  // harness lesson in DEVELOPMENT_LOG entry 58).
  vi.mocked(profiles.get).mockResolvedValue({ id: 'profile-1', name: 'Test Patient' } as never);
  vi.mocked(appointments.get).mockResolvedValue(anAppointment() as never);
  vi.mocked(appointments.checklist).mockResolvedValue({
    appointment_id: 'appointment-1',
    items: [],
  } as never);
  vi.mocked(doctors.list).mockResolvedValue([aDoctor()] as never);
  vi.mocked(visitPrep.get).mockResolvedValue(aPrep() as never);
  vi.mocked(visitPrep.versions).mockResolvedValue([] as never);
});

describe('VisitPrep previous-versions disclosure', () => {
  it('shows nothing at all when the prep has never been regenerated', async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText('Current question')).toBeInTheDocument());
    expect(screen.queryByText(/previous versions/i)).not.toBeInTheDocument();
  });

  it('shows the count collapsed, and the old questions only once expanded', async () => {
    vi.mocked(visitPrep.versions).mockResolvedValue([aVersion()] as never);
    renderPage();

    const toggle = await screen.findByRole('button', { name: /previous versions \(1\)/i });
    // Collapsed by default: history is reference material, not the main event.
    expect(screen.queryByText('An older question')).not.toBeInTheDocument();

    await userEvent.click(toggle);

    expect(await screen.findByText('An older question')).toBeInTheDocument();
    expect(screen.getByText('Older summary')).toBeInTheDocument();
    // The current questions are still there — history is additive, not a swap.
    expect(screen.getByText('Current question')).toBeInTheDocument();
  });

  it('counts every version and labels each one by its version number', async () => {
    vi.mocked(visitPrep.versions).mockResolvedValue([
      aVersion({ id: 'v2', version_number: 2, generated_questions: { A: ['Second oldest'] } }),
      aVersion({ id: 'v1', version_number: 1, generated_questions: { A: ['Oldest'] } }),
    ] as never);
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: /previous versions \(2\)/i }));

    expect(await screen.findByText('Version 2')).toBeInTheDocument();
    expect(screen.getByText('Version 1')).toBeInTheDocument();
    expect(screen.getByText('Second oldest')).toBeInTheDocument();
    expect(screen.getByText('Oldest')).toBeInTheDocument();
  });

  it('offers no way to restore or overwrite from the history', async () => {
    vi.mocked(visitPrep.versions).mockResolvedValue([aVersion()] as never);
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: /previous versions/i }));
    await screen.findByText('An older question');

    // Deliberate: read-only. A restore button would re-raise the overwrite
    // question this issue exists to close.
    expect(screen.queryByRole('button', { name: /restore/i })).not.toBeInTheDocument();
    expect(screen.getByText(/reference only/i)).toBeInTheDocument();
  });

  it('marks a version that was the unreachable-backend placeholder', async () => {
    vi.mocked(visitPrep.versions).mockResolvedValue([aVersion({ used_fallback: true })] as never);
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: /previous versions/i }));

    // Without this, a real generation and issue #47's hardcoded placeholder
    // look identical in the history.
    expect(await screen.findByText(/generic default questions/i)).toBeInTheDocument();
  });
});
