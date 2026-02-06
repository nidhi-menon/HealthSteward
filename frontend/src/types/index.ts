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
}

// Appointment
export interface Appointment {
  id: string;
  profile_id: string;
  doctor_id: string;
  scheduled_date: string;
  purpose: string | null;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppointmentCreate {
  doctor_id: string;
  scheduled_date: string;
  purpose?: string | null;
  status?: string;
  notes?: string | null;
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
