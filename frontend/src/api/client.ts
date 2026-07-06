import type {
  HealthProfile,
  HealthProfileCreate,
  Condition,
  ConditionCreate,
  Medication,
  MedicationCreate,
  Doctor,
  DoctorCreate,
  Appointment,
  AppointmentCreate,
  VisitPrep,
  ScannedFile,
  ParsedItemsResponse,
  ApplyItemsRequest,
  FollowUp,
  LabOrder,
  Referral,
  ActionItems,
  VitalsAlert,
  NudgeState,
} from '../types';

const API_BASE = '/api';

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// Health Profiles
export const profiles = {
  list: () => request<HealthProfile[]>('/profiles/'),
  get: (id: string) => request<HealthProfile>(`/profiles/${id}`),
  create: (data: HealthProfileCreate) =>
    request<HealthProfile>('/profiles/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: Partial<HealthProfileCreate>) =>
    request<HealthProfile>(`/profiles/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/profiles/${id}`, { method: 'DELETE' }),
};

// Conditions
export const conditions = {
  list: (profileId: string) =>
    request<Condition[]>(`/profiles/${profileId}/conditions/`),
  get: (profileId: string, id: string) =>
    request<Condition>(`/profiles/${profileId}/conditions/${id}`),
  create: (profileId: string, data: ConditionCreate) =>
    request<Condition>(`/profiles/${profileId}/conditions/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (profileId: string, id: string, data: Partial<ConditionCreate>) =>
    request<Condition>(`/profiles/${profileId}/conditions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (profileId: string, id: string) =>
    request<void>(`/profiles/${profileId}/conditions/${id}`, {
      method: 'DELETE',
    }),
};

// Medications
export const medications = {
  list: (profileId: string) =>
    request<Medication[]>(`/profiles/${profileId}/medications/`),
  get: (profileId: string, id: string) =>
    request<Medication>(`/profiles/${profileId}/medications/${id}`),
  create: (profileId: string, data: MedicationCreate) =>
    request<Medication>(`/profiles/${profileId}/medications/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (profileId: string, id: string, data: Partial<MedicationCreate>) =>
    request<Medication>(`/profiles/${profileId}/medications/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (profileId: string, id: string) =>
    request<void>(`/profiles/${profileId}/medications/${id}`, {
      method: 'DELETE',
    }),
};

// Doctors
export const doctors = {
  list: (profileId: string) =>
    request<Doctor[]>(`/profiles/${profileId}/doctors/`),
  get: (profileId: string, id: string) =>
    request<Doctor>(`/profiles/${profileId}/doctors/${id}`),
  create: (profileId: string, data: DoctorCreate) =>
    request<Doctor>(`/profiles/${profileId}/doctors/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (profileId: string, id: string, data: Partial<DoctorCreate>) =>
    request<Doctor>(`/profiles/${profileId}/doctors/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (profileId: string, id: string) =>
    request<void>(`/profiles/${profileId}/doctors/${id}`, {
      method: 'DELETE',
    }),
};

// Appointments
export const appointments = {
  list: (profileId: string) =>
    request<Appointment[]>(`/profiles/${profileId}/appointments/`),
  get: (profileId: string, id: string) =>
    request<Appointment>(`/profiles/${profileId}/appointments/${id}`),
  create: (profileId: string, data: AppointmentCreate) =>
    request<Appointment>(`/profiles/${profileId}/appointments/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (profileId: string, id: string, data: Partial<AppointmentCreate>) =>
    request<Appointment>(`/profiles/${profileId}/appointments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (profileId: string, id: string) =>
    request<void>(`/profiles/${profileId}/appointments/${id}`, {
      method: 'DELETE',
    }),
};

// Documents
export const documents = {
  scan: (profileId: string) =>
    request<ScannedFile[]>(`/profiles/${profileId}/documents/scan`),
  parseFile: (profileId: string, filename: string) =>
    request<{ document_id: string; status: string }>(
      `/profiles/${profileId}/documents/parse-file?filename=${encodeURIComponent(filename)}`,
      { method: 'POST' },
    ),
  getParsed: (profileId: string, id: string) =>
    request<ParsedItemsResponse>(`/profiles/${profileId}/documents/${id}/parsed`),
  applyItems: (profileId: string, id: string, items: ApplyItemsRequest) =>
    request<{ status: string; counts: Record<string, number>; action_items: ActionItems }>(
      `/profiles/${profileId}/documents/${id}/apply`,
      {
        method: 'POST',
        body: JSON.stringify(items),
      },
    ),
};

// Action Items
export const actionItems = {
  listFollowUps: (profileId: string, status?: string) =>
    request<FollowUp[]>(`/profiles/${profileId}/follow-ups${status ? `?status=${status}` : ''}`),
  updateFollowUp: (profileId: string, id: string, body: { status?: string; snoozed_until?: string | null }) =>
    request<FollowUp>(`/profiles/${profileId}/follow-ups/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  listLabOrders: (profileId: string, status?: string) =>
    request<LabOrder[]>(`/profiles/${profileId}/lab-orders${status ? `?status=${status}` : ''}`),
  updateLabOrder: (profileId: string, id: string, body: { status?: string; snoozed_until?: string | null }) =>
    request<LabOrder>(`/profiles/${profileId}/lab-orders/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  listReferrals: (profileId: string, status?: string) =>
    request<Referral[]>(`/profiles/${profileId}/referrals${status ? `?status=${status}` : ''}`),
  updateReferral: (profileId: string, id: string, body: { status?: string; snoozed_until?: string | null }) =>
    request<Referral>(`/profiles/${profileId}/referrals/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  pastDueAppointments: (profileId: string) =>
    request<Appointment[]>(`/profiles/${profileId}/past-due-appointments`),
  upcomingWithoutPrep: (profileId: string) =>
    request<Appointment[]>(`/profiles/${profileId}/upcoming-without-prep`),
  vitalsAlerts: (profileId: string) =>
    request<VitalsAlert[]>(`/profiles/${profileId}/vitals-alerts`),
  completedWithoutAvs: (profileId: string) =>
    request<Appointment[]>(`/profiles/${profileId}/completed-without-avs`),
  snoozeNudge: (profileId: string, nudgeType: string, itemId: string, snoozedUntil: string) =>
    request<NudgeState>(`/profiles/${profileId}/nudge-states`, {
      method: 'POST',
      body: JSON.stringify({ nudge_type: nudgeType, item_id: itemId, snoozed_until: snoozedUntil }),
    }),
};

// Visit Prep
export const visitPrep = {
  prepare: (appointmentId: string, additionalConcerns?: string) =>
    request<VisitPrep>(`/visits/${appointmentId}/prepare`, {
      method: 'POST',
      body: JSON.stringify({ additional_concerns: additionalConcerns }),
    }),
  get: (appointmentId: string) =>
    request<VisitPrep>(`/visits/${appointmentId}/prep`),
};
