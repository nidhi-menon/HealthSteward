// Health Profile
export interface HealthProfile {
  id: string;
  name: string;
  date_of_birth: string | null;
  blood_type: string | null;
  allergies: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  created_at: string;
  updated_at: string;
}

export interface HealthProfileCreate {
  name: string;
  date_of_birth?: string | null;
  blood_type?: string | null;
  allergies?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
}

// Condition
export interface Condition {
  id: string;
  profile_id: string;
  name: string;
  icd_10: string | null;
  diagnosed_date: string | null;
  severity: string | null;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConditionCreate {
  name: string;
  diagnosed_date?: string | null;
  severity?: string | null;
  status?: string;
  notes?: string | null;
}

// Medication
export interface Medication {
  id: string;
  profile_id: string;
  name: string;
  dosage: string | null;
  frequency: string | null;
  prescribing_doctor: string | null;
  start_date: string | null;
  end_date: string | null;
  purpose: string | null;
  side_effects: string | null;
  created_at: string;
  updated_at: string;
}

export interface MedicationCreate {
  name: string;
  dosage?: string | null;
  frequency?: string | null;
  prescribing_doctor?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  purpose?: string | null;
  side_effects?: string | null;
}

// Doctor
export interface Doctor {
  id: string;
  profile_id: string;
  name: string;
  specialty: string | null;
  clinic: string | null;
  phone: string | null;
  email: string | null;
  notes: string | null;
  exclude_from_prep_context: boolean;
  created_at: string;
  updated_at: string;
}

export interface DoctorCreate {
  name: string;
  specialty?: string | null;
  clinic?: string | null;
  phone?: string | null;
  email?: string | null;
  notes?: string | null;
  exclude_from_prep_context?: boolean;
}

// Appointment
export interface Appointment {
  id: string;
  profile_id: string;
  doctor_id: string | null;
  scheduled_date: string;
  purpose: string | null;
  status: string;
  prep_notes: string | null;
  visit_notes: string | null;
  visit_notes_updated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppointmentCreate {
  doctor_id: string;
  scheduled_date: string;
  purpose?: string | null;
  status?: string;
  prep_notes?: string | null;
  visit_notes?: string | null;
}

// Visit Prep
export interface VisitPrep {
  id: string;
  appointment_id: string;
  generated_questions: Record<string, string[]> | null;
  context_summary: string | null;
  created_at: string;
  updated_at: string;
}

// Scanned File (from data/avs/ directory)
export interface ScannedFile {
  filename: string;
  file_size_bytes: number;
  modified_date: string;
  status: 'new' | 'pending' | 'parsing' | 'completed' | 'failed';
  document_id: string | null;
}

// Document
export interface Document {
  id: string;
  profile_id: string;
  appointment_id: string | null;
  original_filename: string;
  file_size_bytes: number;
  visit_date: string | null;
  provider_name: string | null;
  facility_name: string | null;
  parse_status: 'pending' | 'parsing' | 'completed' | 'failed';
  parse_error: string | null;
  created_at: string;
  updated_at: string;
}

// Parsed Items (from AVS PDF parsing)
export interface ParsedVitals {
  weight: string | null;
  bmi: number | null;
  blood_pressure: string | null;
  heart_rate: string | null;
  temperature: string | null;
}

export interface ParsedDiagnosis {
  condition: string;
  icd_10: string | null;
  severity: string | null;
  diagnosed_date: string | null;
  status: string | null;
}

export interface ParsedMedicationChange {
  name: string;
  action: 'start' | 'stop' | 'changed';
  strength: string | null;
  instructions: string | null;
  date: string | null;
}

export interface ParsedLabOrder {
  test: string;
  ordered_date: string | null;
}

export interface ParsedReferral {
  specialty: string;
  provider: string | null;
  reason: string | null;
}

export interface ParsedFollowUp {
  description: string;
  timeframe: string | null;
  target_date: string | null;
}

export interface ParsedAppointment {
  description: string;
  date: string | null;
  time: string | null;
  location: string | null;
  phone: string | null;
}

export interface ParsedItemsResponse {
  patient: Record<string, string | null>;
  provider: Record<string, string | null>;
  vitals: ParsedVitals;
  diagnoses: ParsedDiagnosis[];
  medication_changes: ParsedMedicationChange[];
  lab_orders: ParsedLabOrder[];
  referrals: ParsedReferral[];
  follow_up_recommended: ParsedFollowUp[];
  upcoming_appointments: ParsedAppointment[];
  notes: string[];
}

// Action Items (from parsed AVS documents)
export interface FollowUp {
  id: string;
  profile_id: string;
  document_id: string;
  description: string;
  timeframe: string | null;
  target_date: string | null;
  status: string;
  snoozed_until: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface LabOrder {
  id: string;
  profile_id: string;
  document_id: string;
  test_name: string;
  ordered_date: string | null;
  status: string;
  snoozed_until: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Referral {
  id: string;
  profile_id: string;
  document_id: string;
  specialty: string;
  provider_name: string | null;
  reason: string | null;
  status: string;
  snoozed_until: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface NudgeState {
  id: string;
  profile_id: string;
  nudge_type: string;
  item_id: string;
  snoozed_until: string;
}

export interface VitalsAlert {
  metric: string;
  message: string;
  direction: 'up' | 'down';
  oldest_value: string;
  newest_value: string;
  visit_count: number;
}

export interface ActionItems {
  follow_ups: FollowUp[];
  lab_orders: LabOrder[];
  referrals: Referral[];
}

export interface ApplyItemsRequest {
  diagnoses: ParsedDiagnosis[];
  medication_starts: ParsedMedicationChange[];
  medication_stops: ParsedMedicationChange[];
  medication_updates: ParsedMedicationChange[];
  vitals: ParsedVitals | null;
  lab_orders: ParsedLabOrder[];
  referrals: ParsedReferral[];
  follow_ups: ParsedFollowUp[];
  appointments: ParsedAppointment[];
}

// App Settings (DEC-016)
export type LlmProvider = 'claude' | 'ollama' | 'custom';

export interface AppSettings {
  llm_provider: LlmProvider;
  anthropic_api_key: string | null; // masked, e.g. "...ab12"
  anthropic_model: string;
  ollama_base_url: string;
  ollama_model: string;
  custom_llm_base_url: string | null;
  custom_llm_api_key: string | null; // masked
  custom_llm_model: string | null;
}

export interface AppSettingsUpdate {
  llm_provider?: LlmProvider;
  anthropic_api_key?: string;
  anthropic_model?: string;
  ollama_base_url?: string;
  ollama_model?: string;
  custom_llm_base_url?: string;
  custom_llm_api_key?: string;
  custom_llm_model?: string;
}
