import type {
  Appointment,
  Doctor,
  FollowUp,
  LabOrder,
  Referral,
  SnoozedItem,
} from '../types';

/**
 * Builders rather than fixed objects: a test should state only the fields it
 * cares about, so the assertion reads as the reason the test exists.
 */

export function aDoctor(overrides: Partial<Doctor> = {}): Doctor {
  return {
    id: 'doctor-1',
    profile_id: 'profile-1',
    name: 'Dr. Ada Reyes',
    specialty: 'Cardiology',
    clinic: null,
    phone: null,
    email: null,
    notes: null,
    exclude_from_prep_context: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

export function anAppointment(overrides: Partial<Appointment> = {}): Appointment {
  return {
    id: 'appointment-1',
    profile_id: 'profile-1',
    doctor_id: 'doctor-1',
    scheduled_date: '2026-06-15T10:00:00Z',
    purpose: 'Quarterly checkup',
    status: 'scheduled',
    prep_notes: null,
    visit_notes: null,
    visit_notes_updated_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

export function aFollowUp(overrides: Partial<FollowUp> = {}): FollowUp {
  return {
    id: 'follow-up-1',
    profile_id: 'profile-1',
    document_id: 'document-1',
    description: 'Recheck blood pressure',
    timeframe: '3 months',
    target_date: null,
    status: 'pending',
    snoozed_until: null,
    completed_at: null,
    created_at: '2026-06-01T00:00:00Z',
    ...overrides,
  };
}

export function aLabOrder(overrides: Partial<LabOrder> = {}): LabOrder {
  return {
    id: 'lab-order-1',
    profile_id: 'profile-1',
    document_id: 'document-1',
    test_name: 'Lipid panel',
    ordered_date: '2026-06-01',
    status: 'ordered',
    snoozed_until: null,
    completed_at: null,
    created_at: '2026-06-01T00:00:00Z',
    ...overrides,
  };
}

export function aReferral(overrides: Partial<Referral> = {}): Referral {
  return {
    id: 'referral-1',
    profile_id: 'profile-1',
    document_id: 'document-1',
    specialty: 'Endocrinology',
    provider_name: null,
    reason: null,
    status: 'pending',
    snoozed_until: null,
    completed_at: null,
    created_at: '2026-06-01T00:00:00Z',
    ...overrides,
  };
}

export function aSnoozedItem(overrides: Partial<SnoozedItem> = {}): SnoozedItem {
  return {
    category: 'follow_up',
    category_label: 'Follow-up',
    item_id: 'follow-up-1',
    label: 'Recheck blood pressure',
    snoozed_until: '2026-06-20T00:00:00Z',
    ...overrides,
  };
}
