import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { profiles, conditions, medications, doctors, appointments } from '../api/client';
import { formatDateString } from '../utils/date';
import { Card, CardHeader, CardContent } from '../components/Card';
import { Button } from '../components/Button';
import { Modal, DeleteConfirmModal } from '../components/Modal';
import { Input, Textarea, Select, MonthYearInput, DatePicker } from '../components/Input';
import type { ConditionCreate, MedicationCreate, DoctorCreate, AppointmentCreate, Doctor } from '../types';

type Tab = 'overview' | 'conditions' | 'medications' | 'doctors' | 'appointments';

export default function ProfileDetail() {
  const { profileId } = useParams<{ profileId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [modalType, setModalType] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Queries
  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['profile', profileId],
    queryFn: () => profiles.get(profileId!),
    enabled: !!profileId,
  });

  const { data: conditionList } = useQuery({
    queryKey: ['conditions', profileId],
    queryFn: () => conditions.list(profileId!),
    enabled: !!profileId,
  });

  const { data: medicationList } = useQuery({
    queryKey: ['medications', profileId],
    queryFn: () => medications.list(profileId!),
    enabled: !!profileId,
  });

  const { data: doctorList } = useQuery({
    queryKey: ['doctors', profileId],
    queryFn: () => doctors.list(profileId!),
    enabled: !!profileId,
  });

  const { data: appointmentList } = useQuery({
    queryKey: ['appointments', profileId],
    queryFn: () => appointments.list(profileId!),
    enabled: !!profileId,
  });

  // Delete profile mutation
  const deleteMutation = useMutation({
    mutationFn: () => profiles.delete(profileId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      navigate('/');
    },
  });

  if (profileLoading) {
    return <div className="text-center py-12 text-gray-500">Loading...</div>;
  }

  if (!profile) {
    return <div className="text-center py-12 text-gray-500">Profile not found</div>;
  }

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'conditions', label: 'Conditions', count: conditionList?.length },
    { id: 'medications', label: 'Medications', count: medicationList?.length },
    { id: 'doctors', label: 'Doctors', count: doctorList?.length },
    { id: 'appointments', label: 'Appointments', count: appointmentList?.length },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/" className="text-gray-400 hover:text-gray-600">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">{profile.name}</h1>
          {profile.blood_type && <span className="text-gray-500">Blood Type: {profile.blood_type}</span>}
        </div>
        <Button variant="danger" size="sm" onClick={() => setShowDeleteConfirm(true)}>
          Delete Profile
        </Button>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-3 border-b-2 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'border-emerald-500 text-emerald-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span className="ml-2 bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full text-xs">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <OverviewTab profile={profile} />
      )}

      {activeTab === 'conditions' && (
        <ConditionsTab
          profileId={profileId!}
          conditions={conditionList || []}
          onAdd={() => setModalType('condition')}
        />
      )}

      {activeTab === 'medications' && (
        <MedicationsTab
          profileId={profileId!}
          medications={medicationList || []}
          onAdd={() => setModalType('medication')}
        />
      )}

      {activeTab === 'doctors' && (
        <DoctorsTab
          profileId={profileId!}
          doctors={doctorList || []}
          onAdd={() => setModalType('doctor')}
        />
      )}

      {activeTab === 'appointments' && (
        <AppointmentsTab
          profileId={profileId!}
          appointments={appointmentList || []}
          doctors={doctorList || []}
          onAdd={() => setModalType('appointment')}
        />
      )}

      {/* Modals */}
      <ConditionModal
        isOpen={modalType === 'condition'}
        onClose={() => setModalType(null)}
        profileId={profileId!}
      />
      <MedicationModal
        isOpen={modalType === 'medication'}
        onClose={() => setModalType(null)}
        profileId={profileId!}
      />
      <DoctorModal
        isOpen={modalType === 'doctor'}
        onClose={() => setModalType(null)}
        profileId={profileId!}
      />
      <AppointmentModal
        isOpen={modalType === 'appointment'}
        onClose={() => setModalType(null)}
        profileId={profileId!}
        doctors={doctorList || []}
      />
      <DeleteConfirmModal
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={() => deleteMutation.mutate()}
        title="Delete Health Profile"
        itemName={profile.name}
        itemType="profile"
        isDeleting={deleteMutation.isPending}
      />
    </div>
  );
}

// Overview Tab
function OverviewTab({ profile }: { profile: any }) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card>
        <CardHeader>
          <h3 className="font-semibold text-gray-900">Personal Information</h3>
        </CardHeader>
        <CardContent className="space-y-3">
          <InfoRow label="Name" value={profile.name} />
          <InfoRow label="Date of Birth" value={formatDateString(profile.date_of_birth)} />
          <InfoRow label="Blood Type" value={profile.blood_type || '-'} />
          <InfoRow label="Allergies" value={profile.allergies || 'None recorded'} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h3 className="font-semibold text-gray-900">Emergency Contact</h3>
        </CardHeader>
        <CardContent className="space-y-3">
          <InfoRow label="Name" value={profile.emergency_contact_name || '-'} />
          <InfoRow label="Phone" value={profile.emergency_contact_phone || '-'} />
        </CardContent>
      </Card>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-900 font-medium">{value}</span>
    </div>
  );
}

// Conditions Tab
function ConditionsTab({ profileId, conditions: conditionList, onAdd }: { profileId: string; conditions: any[]; onAdd: () => void }) {
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (conditionId: string) => conditions.delete(profileId, conditionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conditions', profileId] });
      setDeleteTarget(null);
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-gray-900">Medical Conditions</h3>
        <Button size="sm" onClick={onAdd}>+ Add Condition</Button>
      </div>
      {conditionList.length === 0 ? (
        <Card>
          <CardContent className="text-center py-8 text-gray-500">
            No conditions recorded
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {conditionList.map((condition: any) => (
            <Card key={condition.id}>
              <CardContent>
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h4 className="font-medium text-gray-900">{condition.name}</h4>
                    <div className="flex gap-4 mt-1 text-sm text-gray-500">
                      {condition.severity && <span>Severity: {condition.severity}</span>}
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        condition.status === 'active' ? 'bg-red-100 text-red-700' :
                        condition.status === 'managed' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {condition.status}
                      </span>
                    </div>
                    {condition.notes && <p className="mt-2 text-sm text-gray-600">{condition.notes}</p>}
                  </div>
                  <button
                    onClick={() => setDeleteTarget({ id: condition.id, name: condition.name })}
                    className="text-gray-400 hover:text-red-600 transition-colors p-1"
                    title="Delete condition"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete Condition"
      >
        <div className="space-y-4">
          <p className="text-gray-600">
            Are you sure you want to delete <strong>"{deleteTarget?.name}"</strong>? This action cannot be undone.
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// Medications Tab
function MedicationsTab({ profileId, medications: medicationList, onAdd }: { profileId: string; medications: any[]; onAdd: () => void }) {
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (medicationId: string) => medications.delete(profileId, medicationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medications', profileId] });
      setDeleteTarget(null);
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-gray-900">Medications</h3>
        <Button size="sm" onClick={onAdd}>+ Add Medication</Button>
      </div>
      {medicationList.length === 0 ? (
        <Card>
          <CardContent className="text-center py-8 text-gray-500">
            No medications recorded
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {medicationList.map((med: any) => (
            <Card key={med.id}>
              <CardContent>
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h4 className="font-medium text-gray-900">{med.name}</h4>
                    <div className="flex gap-4 mt-1 text-sm text-gray-500">
                      {med.dosage && <span>{med.dosage}</span>}
                      {med.frequency && <span>• {med.frequency}</span>}
                    </div>
                    {med.purpose && <p className="mt-2 text-sm text-gray-600">Purpose: {med.purpose}</p>}
                  </div>
                  <button
                    onClick={() => setDeleteTarget({ id: med.id, name: med.name })}
                    className="text-gray-400 hover:text-red-600 transition-colors p-1"
                    title="Delete medication"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete Medication"
      >
        <div className="space-y-4">
          <p className="text-gray-600">
            Are you sure you want to delete <strong>"{deleteTarget?.name}"</strong>? This action cannot be undone.
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// Doctors Tab
function DoctorsTab({ profileId, doctors: doctorList, onAdd }: { profileId: string; doctors: any[]; onAdd: () => void }) {
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (doctorId: string) => doctors.delete(profileId, doctorId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['doctors', profileId] });
      setDeleteTarget(null);
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-gray-900">Healthcare Providers</h3>
        <Button size="sm" onClick={onAdd}>+ Add Doctor</Button>
      </div>
      {doctorList.length === 0 ? (
        <Card>
          <CardContent className="text-center py-8 text-gray-500">
            No doctors recorded
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {doctorList.map((doc: any) => (
            <Card key={doc.id}>
              <CardContent>
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h4 className="font-medium text-gray-900">{doc.name}</h4>
                    {doc.specialty && <p className="text-sm text-emerald-600">{doc.specialty}</p>}
                    {doc.clinic && <p className="text-sm text-gray-500 mt-1">{doc.clinic}</p>}
                    <div className="mt-2 space-y-1 text-sm text-gray-500">
                      {doc.phone && <p>📞 {doc.phone}</p>}
                      {doc.email && <p>✉️ {doc.email}</p>}
                    </div>
                  </div>
                  <button
                    onClick={() => setDeleteTarget({ id: doc.id, name: doc.name })}
                    className="text-gray-400 hover:text-red-600 transition-colors p-1"
                    title="Delete doctor"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete Doctor"
      >
        <div className="space-y-4">
          <p className="text-gray-600">
            Are you sure you want to delete <strong>"{deleteTarget?.name}"</strong>? This will also remove any appointments with this doctor.
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// Appointments Tab
function AppointmentsTab({ profileId, appointments: appointmentList, doctors: doctorList, onAdd }: { profileId: string; appointments: any[]; doctors: any[]; onAdd: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const getDoctorName = (doctorId: string) => {
    const doc = doctorList.find((d: any) => d.id === doctorId);
    return doc?.name || 'Unknown Doctor';
  };

  const deleteMutation = useMutation({
    mutationFn: (appointmentId: string) => appointments.delete(profileId, appointmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments', profileId] });
      setDeleteTarget(null);
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-gray-900">Appointments</h3>
        <Button size="sm" onClick={onAdd} disabled={doctorList.length === 0}>
          + Schedule Appointment
        </Button>
      </div>
      {doctorList.length === 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
          Add a doctor first before scheduling appointments
        </div>
      )}
      {appointmentList.length === 0 ? (
        <Card>
          <CardContent className="text-center py-8 text-gray-500">
            No appointments scheduled
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {appointmentList.map((appt: any) => (
            <Card key={appt.id} className="hover:border-emerald-300 transition-colors">
              <CardContent>
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h4 className="font-medium text-gray-900">{getDoctorName(appt.doctor_id)}</h4>
                    <p className="text-sm text-gray-500">
                      {new Date(appt.scheduled_date).toLocaleString()}
                    </p>
                    {appt.purpose && <p className="mt-1 text-sm text-gray-600">{appt.purpose}</p>}
                    <span className={`inline-block mt-2 px-2 py-0.5 rounded-full text-xs ${
                      appt.status === 'scheduled' ? 'bg-blue-100 text-blue-700' :
                      appt.status === 'completed' ? 'bg-green-100 text-green-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {appt.status}
                    </span>
                    {appt.prep_notes && (
                      <div className="mt-2 p-2 bg-blue-50 rounded text-sm">
                        <span className="font-medium text-blue-700">Pre-visit notes: </span>
                        <span className="text-blue-900">{appt.prep_notes}</span>
                      </div>
                    )}
                    {appt.visit_notes && (
                      <div className="mt-2 p-2 bg-green-50 rounded text-sm">
                        <span className="font-medium text-green-700">Visit notes: </span>
                        <span className="text-green-900">{appt.visit_notes}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-start gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => navigate(`/profiles/${profileId}/appointments/${appt.id}/prep`)}
                    >
                      {appt.status === 'completed' ? 'View Details' : 'Prepare Visit'}
                    </Button>
                    <button
                      onClick={() => setDeleteTarget({ id: appt.id, name: `${getDoctorName(appt.doctor_id)} - ${new Date(appt.scheduled_date).toLocaleDateString()}` })}
                      className="text-gray-400 hover:text-red-600 transition-colors p-1"
                      title="Delete appointment"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete Appointment"
      >
        <div className="space-y-4">
          <p className="text-gray-600">
            Are you sure you want to delete the appointment <strong>"{deleteTarget?.name}"</strong>? This will also remove any visit prep and notes.
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// Condition Modal
function ConditionModal({ isOpen, onClose, profileId }: { isOpen: boolean; onClose: () => void; profileId: string }) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<ConditionCreate>({ name: '', status: 'active' });

  const mutation = useMutation({
    mutationFn: (data: ConditionCreate) => conditions.create(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conditions', profileId] });
      onClose();
      setFormData({ name: '', status: 'active' });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Condition">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Condition Name *" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
        <MonthYearInput label="Diagnosed (Month/Year)" value={formData.diagnosed_date || null} onChange={(value) => setFormData({ ...formData, diagnosed_date: value })} />
        <Select label="Severity" value={formData.severity || ''} onChange={(e) => setFormData({ ...formData, severity: e.target.value || null })} options={[{ value: '', label: 'Select severity' }, { value: 'mild', label: 'Mild' }, { value: 'moderate', label: 'Moderate' }, { value: 'severe', label: 'Severe' }]} />
        <Select label="Status" value={formData.status || 'active'} onChange={(e) => setFormData({ ...formData, status: e.target.value })} options={[{ value: 'active', label: 'Active' }, { value: 'managed', label: 'Managed' }, { value: 'resolved', label: 'Resolved' }]} />
        <Textarea label="Notes" value={formData.notes || ''} onChange={(e) => setFormData({ ...formData, notes: e.target.value || null })} />
        <div className="flex justify-end gap-3 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Adding...' : 'Add Condition'}</Button>
        </div>
      </form>
    </Modal>
  );
}

// Medication Modal
function MedicationModal({ isOpen, onClose, profileId }: { isOpen: boolean; onClose: () => void; profileId: string }) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<MedicationCreate>({ name: '' });

  const mutation = useMutation({
    mutationFn: (data: MedicationCreate) => medications.create(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medications', profileId] });
      onClose();
      setFormData({ name: '' });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Medication">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Medication Name *" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
        <Input label="Dosage" value={formData.dosage || ''} onChange={(e) => setFormData({ ...formData, dosage: e.target.value || null })} placeholder="e.g., 500mg" />
        <Input label="Frequency" value={formData.frequency || ''} onChange={(e) => setFormData({ ...formData, frequency: e.target.value || null })} placeholder="e.g., twice daily" />
        <Input label="Prescribing Doctor" value={formData.prescribing_doctor || ''} onChange={(e) => setFormData({ ...formData, prescribing_doctor: e.target.value || null })} />
        <DatePicker label="Start Date" value={formData.start_date || null} onChange={(value) => setFormData({ ...formData, start_date: value })} />
        <Textarea label="Purpose" value={formData.purpose || ''} onChange={(e) => setFormData({ ...formData, purpose: e.target.value || null })} />
        <div className="flex justify-end gap-3 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Adding...' : 'Add Medication'}</Button>
        </div>
      </form>
    </Modal>
  );
}

// Doctor Modal
function DoctorModal({ isOpen, onClose, profileId }: { isOpen: boolean; onClose: () => void; profileId: string }) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<DoctorCreate>({ name: '' });

  const mutation = useMutation({
    mutationFn: (data: DoctorCreate) => doctors.create(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['doctors', profileId] });
      onClose();
      setFormData({ name: '' });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Doctor">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Doctor Name *" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
        <Input label="Specialty" value={formData.specialty || ''} onChange={(e) => setFormData({ ...formData, specialty: e.target.value || null })} placeholder="e.g., Cardiology" />
        <Input label="Clinic/Hospital" value={formData.clinic || ''} onChange={(e) => setFormData({ ...formData, clinic: e.target.value || null })} />
        <Input label="Phone" value={formData.phone || ''} onChange={(e) => setFormData({ ...formData, phone: e.target.value || null })} />
        <Input label="Email" type="email" value={formData.email || ''} onChange={(e) => setFormData({ ...formData, email: e.target.value || null })} />
        <Textarea label="Notes" value={formData.notes || ''} onChange={(e) => setFormData({ ...formData, notes: e.target.value || null })} />
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="exclude_from_prep"
            checked={formData.exclude_from_prep_context || false}
            onChange={(e) => setFormData({ ...formData, exclude_from_prep_context: e.target.checked })}
            className="h-4 w-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
          />
          <label htmlFor="exclude_from_prep" className="text-sm text-gray-700">
            Exclude from visit prep context (for sensitive specialties)
          </label>
        </div>
        <div className="flex justify-end gap-3 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Adding...' : 'Add Doctor'}</Button>
        </div>
      </form>
    </Modal>
  );
}

// Appointment Modal
function AppointmentModal({ isOpen, onClose, profileId, doctors }: { isOpen: boolean; onClose: () => void; profileId: string; doctors: Doctor[] }) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<AppointmentCreate>({
    doctor_id: doctors[0]?.id || '',
    scheduled_date: '',
    status: 'scheduled',
  });

  const mutation = useMutation({
    mutationFn: (data: AppointmentCreate) => appointments.create(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments', profileId] });
      onClose();
      setFormData({ doctor_id: doctors[0]?.id || '', scheduled_date: '', status: 'scheduled' });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Schedule Appointment">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Select
          label="Doctor *"
          value={formData.doctor_id}
          onChange={(e) => setFormData({ ...formData, doctor_id: e.target.value })}
          options={doctors.map((d) => ({ value: d.id, label: `${d.name}${d.specialty ? ` (${d.specialty})` : ''}` }))}
        />
        <Input
          label="Date & Time *"
          type="datetime-local"
          value={formData.scheduled_date}
          onChange={(e) => setFormData({ ...formData, scheduled_date: e.target.value })}
          required
        />
        <Input label="Purpose" value={formData.purpose || ''} onChange={(e) => setFormData({ ...formData, purpose: e.target.value || null })} placeholder="e.g., Annual checkup" />
        <Textarea label="Pre-Visit Notes" value={formData.prep_notes || ''} onChange={(e) => setFormData({ ...formData, prep_notes: e.target.value || null })} placeholder="Questions or concerns to discuss" />
        <div className="flex justify-end gap-3 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Scheduling...' : 'Schedule'}</Button>
        </div>
      </form>
    </Modal>
  );
}
