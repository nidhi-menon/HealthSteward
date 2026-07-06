import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { profiles, conditions, medications, doctors, appointments, documents } from '../api/client';
import { formatDateString } from '../utils/date';
import { Card, CardHeader, CardContent } from '../components/Card';
import { Button } from '../components/Button';
import { Modal, DeleteConfirmModal } from '../components/Modal';
import { Input, Textarea, Select, MonthYearInput, DatePicker } from '../components/Input';
import { DocumentCard } from '../components/DocumentCard';
import { ParsedItemsReview } from '../components/ParsedItemsReview';
import { PostAvsActionPanel } from '../components/PostAvsActionPanel';
import { ActionItemsSection } from '../components/ActionItemsSection';
import type { Condition, ConditionCreate, Medication, MedicationCreate, Doctor, DoctorCreate, Appointment, AppointmentCreate, ScannedFile, ParsedItemsResponse, ApplyItemsRequest, ActionItems } from '../types';

type Tab = 'overview' | 'conditions' | 'medications' | 'doctors' | 'appointments' | 'documents';

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

  const { data: scannedFiles } = useQuery({
    queryKey: ['scannedFiles', profileId],
    queryFn: () => documents.scan(profileId!),
    enabled: !!profileId,
    refetchInterval: 30_000,
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
    { id: 'documents', label: 'Documents', count: scannedFiles?.length },
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
        <OverviewTab profile={profile} profileId={profileId!} appointments={appointmentList || []} doctors={doctorList || []} />
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
          scannedFiles={scannedFiles || []}
          onAdd={() => setModalType('appointment')}
        />
      )}

      {activeTab === 'documents' && (
        <DocumentsTab
          profileId={profileId!}
          files={scannedFiles || []}
          appointments={appointmentList || []}
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
function OverviewTab({ profile, profileId, appointments, doctors }: { profile: any; profileId: string; appointments: Appointment[]; doctors: Doctor[] }) {
  return (
    <div className="space-y-6">
    <ActionItemsSection profileId={profileId} appointments={appointments} doctors={doctors} />
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
  const [editTarget, setEditTarget] = useState<Condition | null>(null);

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
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium text-gray-900">{condition.name}</h4>
                      {condition.icd_10 && (
                        <span className="px-1.5 py-0.5 rounded text-xs font-mono bg-purple-50 text-purple-700">{condition.icd_10}</span>
                      )}
                    </div>
                    <div className="flex gap-4 mt-1 text-sm text-gray-500">
                      {condition.diagnosed_date && <span>Diagnosed: {formatDateString(condition.diagnosed_date)}</span>}
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
                  <div className="flex gap-1">
                    <button
                      onClick={() => setEditTarget(condition)}
                      className="text-gray-400 hover:text-emerald-600 transition-colors p-1"
                      title="Edit condition"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
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
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Edit Condition Modal */}
      <ConditionModal
        isOpen={editTarget !== null}
        onClose={() => setEditTarget(null)}
        profileId={profileId}
        condition={editTarget ?? undefined}
      />

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
  const [editTarget, setEditTarget] = useState<Medication | null>(null);

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
                  <div className="flex gap-1">
                    <button
                      onClick={() => setEditTarget(med)}
                      className="text-gray-400 hover:text-emerald-600 transition-colors p-1"
                      title="Edit medication"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
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
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <MedicationModal
        isOpen={editTarget !== null}
        onClose={() => setEditTarget(null)}
        profileId={profileId}
        medication={editTarget ?? undefined}
      />

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
  const [editTarget, setEditTarget] = useState<Doctor | null>(null);

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
                      {doc.phone && <p>Ph: {doc.phone}</p>}
                      {doc.email && <p>Em: {doc.email}</p>}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setEditTarget(doc)}
                      className="text-gray-400 hover:text-emerald-600 transition-colors p-1"
                      title="Edit doctor"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
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
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <DoctorModal
        isOpen={editTarget !== null}
        onClose={() => setEditTarget(null)}
        profileId={profileId}
        doctor={editTarget ?? undefined}
      />

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
function AppointmentsTab({ profileId, appointments: appointmentList, doctors: doctorList, scannedFiles, onAdd }: { profileId: string; appointments: any[]; doctors: any[]; scannedFiles: ScannedFile[]; onAdd: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const [editTarget, setEditTarget] = useState<Appointment | null>(null);

  const getDoctorName = (doctorId: string | null) => {
    if (!doctorId) return null;
    const doc = doctorList.find((d: any) => d.id === doctorId);
    return doc?.name || 'Unknown Doctor';
  };

  const deleteMutation = useMutation({
    mutationFn: (appointmentId: string) => appointments.delete(profileId, appointmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments', profileId] });
      queryClient.invalidateQueries({ queryKey: ['pastDueAppointments', profileId] });
      queryClient.invalidateQueries({ queryKey: ['completedWithoutAvs', profileId] });
      setDeleteTarget(null);
    },
  });

  const now = new Date();
  const upcomingIn30Days = appointmentList.filter(a => {
    if (a.status !== 'scheduled') return false;
    const d = new Date(a.scheduled_date);
    const diffDays = (d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
    return diffDays >= 0 && diffDays <= 30;
  });
  const unprocessedFiles = scannedFiles.filter(f => f.status === 'new');
  const showAvsNudge = upcomingIn30Days.length > 0 && unprocessedFiles.length > 0;

  return (
    <div className="space-y-4">
      {showAvsNudge && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
          <span className="font-medium">Heads up:</span> You have {upcomingIn30Days.length === 1 ? 'an appointment' : `${upcomingIn30Days.length} appointments`} in the next 30 days and{' '}
          {unprocessedFiles.length === 1 ? '1 unprocessed document' : `${unprocessedFiles.length} unprocessed documents`} in your AVS folder.
          {' '}<span className="font-medium">Process them now</span> to keep your profile current before your visit.
        </div>
      )}
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
                    <h4 className="font-medium text-gray-900">
                      {getDoctorName(appt.doctor_id) || appt.purpose || 'Appointment'}
                    </h4>
                    <p className="text-sm text-gray-500">
                      {new Date(appt.scheduled_date).toLocaleString()}
                    </p>
                    {appt.purpose && getDoctorName(appt.doctor_id) && (
                      <p className="mt-1 text-sm text-gray-600">{appt.purpose}</p>
                    )}
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
                      onClick={() => setEditTarget(appt)}
                      className="text-gray-400 hover:text-emerald-600 transition-colors p-1"
                      title="Edit appointment"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => setDeleteTarget({ id: appt.id, name: `${getDoctorName(appt.doctor_id) || appt.purpose || 'Appointment'} - ${new Date(appt.scheduled_date).toLocaleDateString()}` })}
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

      <AppointmentModal
        isOpen={editTarget !== null}
        onClose={() => setEditTarget(null)}
        profileId={profileId}
        doctors={doctorList}
        appointment={editTarget ?? undefined}
      />

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

// Documents Tab
type DocView = 'list' | 'review';

function DocumentsTab({ profileId, files, appointments: appointmentList }: { profileId: string; files: ScannedFile[]; appointments: Appointment[] }) {
  const queryClient = useQueryClient();
  const [view, setView] = useState<DocView>('list');
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [parsedData, setParsedData] = useState<ParsedItemsResponse | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [parsingFilename, setParsingFilename] = useState<string | null>(null);
  const [postAvsItems, setPostAvsItems] = useState<ActionItems | null>(null);

  const handleParse = async (filename: string, documentId: string | null) => {
    setIsParsing(true);
    setParseError(null);
    setParsingFilename(filename);

    try {
      // If no document record exists yet, create one
      let docId = documentId;
      if (!docId) {
        const result = await documents.parseFile(profileId, filename);
        docId = result.document_id;
      }
      setActiveDocId(docId);

      // Trigger parse and get results
      const parsed = await documents.getParsed(profileId, docId);
      setParsedData(parsed);
      setView('review');
      setIsParsing(false);
      queryClient.invalidateQueries({ queryKey: ['scannedFiles', profileId] });
    } catch (err: any) {
      if (err.message?.includes('202') || err.message?.includes('Parsing in progress')) {
        // Need to poll — get the docId first if we don't have it
        if (!activeDocId) {
          // The parseFile call should have set it
        }
        pollForParsed(activeDocId!);
      } else {
        setParseError(err.message || 'Parsing failed');
        setIsParsing(false);
        queryClient.invalidateQueries({ queryKey: ['scannedFiles', profileId] });
      }
    }
  };

  const pollForParsed = (docId: string) => {
    const interval = setInterval(async () => {
      try {
        const result = await documents.getParsed(profileId, docId);
        clearInterval(interval);
        setParsedData(result);
        setView('review');
        setIsParsing(false);
        queryClient.invalidateQueries({ queryKey: ['scannedFiles', profileId] });
      } catch (err: any) {
        if (!err.message?.includes('202') && !err.message?.includes('Parsing in progress')) {
          clearInterval(interval);
          setParseError(err.message || 'Parsing failed');
          setIsParsing(false);
          queryClient.invalidateQueries({ queryKey: ['scannedFiles', profileId] });
        }
      }
    }, 3000);
    setTimeout(() => {
      clearInterval(interval);
      setParseError('Parsing timed out. Please try again.');
      setIsParsing(false);
    }, 300000);
  };

  const applyMutation = useMutation({
    mutationFn: (items: ApplyItemsRequest) => documents.applyItems(profileId, activeDocId!, items),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['conditions', profileId] });
      queryClient.invalidateQueries({ queryKey: ['medications', profileId] });
      queryClient.invalidateQueries({ queryKey: ['doctors', profileId] });
      queryClient.invalidateQueries({ queryKey: ['appointments', profileId] });
      queryClient.invalidateQueries({ queryKey: ['scannedFiles', profileId] });
      queryClient.invalidateQueries({ queryKey: ['followUps', profileId] });
      queryClient.invalidateQueries({ queryKey: ['labOrders', profileId] });
      queryClient.invalidateQueries({ queryKey: ['referrals', profileId] });
      queryClient.invalidateQueries({ queryKey: ['completedWithoutAvs', profileId] });
      setParsedData(null);
      setActiveDocId(null);
      setView('list');
      if (result.action_items) {
        const { follow_ups, lab_orders, referrals } = result.action_items;
        if (follow_ups.length || lab_orders.length || referrals.length) {
          setPostAvsItems(result.action_items);
        }
      }
    },
  });

  if (view === 'review' && parsedData) {
    return (
      <ParsedItemsReview
        data={parsedData}
        onApply={(items) => applyMutation.mutate(items)}
        onBack={() => {
          setView('list');
          setParsedData(null);
          setActiveDocId(null);
        }}
        isApplying={applyMutation.isPending}
      />
    );
  }

  // Separate new files from processed ones
  const newFiles = files.filter(f => f.status === 'new');
  const processedFiles = files.filter(f => f.status !== 'new');

  // List view
  return (
    <div className="space-y-4">
      {postAvsItems && (
        <PostAvsActionPanel
          profileId={profileId}
          actionItems={postAvsItems}
          upcomingAppointments={appointmentList}
          onDismiss={() => setPostAvsItems(null)}
        />
      )}

      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-gray-900">Documents</h3>
        <span className="text-sm text-gray-500">
          Scanning <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">data/avs/</code>
          <span className="ml-2 text-xs text-gray-400">· auto-refreshes every 30s</span>
        </span>
      </div>

      {isParsing && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center gap-3">
          <svg className="animate-spin h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span className="text-sm text-blue-700">Parsing document with local LLM... This may take a minute.</span>
        </div>
      )}

      {parseError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {parseError}
        </div>
      )}

      {files.length === 0 ? (
        <Card>
          <CardContent className="text-center py-8 text-gray-500">
            <p>No PDFs found in <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">data/avs/</code></p>
            <p className="mt-2 text-sm">Drop your after-visit summary PDFs there to get started.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {newFiles.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-purple-700">New — ready to parse</h4>
              {newFiles.map((file) => (
                <DocumentCard
                  key={file.filename}
                  file={file}
                  onParse={handleParse}
                  isParsing={isParsing && parsingFilename === file.filename}
                />
              ))}
            </div>
          )}
          {processedFiles.length > 0 && (
            <div className="space-y-3">
              {newFiles.length > 0 && (
                <h4 className="text-sm font-medium text-gray-500">Previously processed</h4>
              )}
              {processedFiles.map((file) => (
                <DocumentCard
                  key={file.filename}
                  file={file}
                  onParse={handleParse}
                  isParsing={isParsing && parsingFilename === file.filename}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Condition Modal (supports both create and edit)
function ConditionModal({ isOpen, onClose, profileId, condition }: { isOpen: boolean; onClose: () => void; profileId: string; condition?: Condition }) {
  const queryClient = useQueryClient();
  const isEdit = !!condition;
  const [formData, setFormData] = useState<ConditionCreate>({ name: '', status: 'active' });
  const [showConfirm, setShowConfirm] = useState(false);

  // Reset form when modal opens/condition changes
  const resetKey = condition?.id ?? 'new';
  const [lastResetKey, setLastResetKey] = useState(resetKey);
  if (resetKey !== lastResetKey) {
    setLastResetKey(resetKey);
    if (condition) {
      setFormData({
        name: condition.name,
        diagnosed_date: condition.diagnosed_date,
        severity: condition.severity,
        status: condition.status,
        notes: condition.notes,
      });
    } else {
      setFormData({ name: '', status: 'active' });
    }
    setShowConfirm(false);
  }

  const createMutation = useMutation({
    mutationFn: (data: ConditionCreate) => conditions.create(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conditions', profileId] });
      handleClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: ConditionCreate) => conditions.update(profileId, condition!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conditions', profileId] });
      handleClose();
    },
  });

  const mutation = isEdit ? updateMutation : createMutation;

  const handleClose = () => {
    setFormData({ name: '', status: 'active' });
    setShowConfirm(false);
    onClose();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isEdit) {
      setShowConfirm(true);
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleConfirmEdit = () => {
    updateMutation.mutate(formData);
  };

  // Build list of changed fields for confirmation
  const changedFields: { label: string; from: string; to: string }[] = [];
  if (isEdit && condition) {
    if (formData.name !== condition.name) changedFields.push({ label: 'Name', from: condition.name, to: formData.name });
    if ((formData.diagnosed_date || null) !== (condition.diagnosed_date || null)) changedFields.push({ label: 'Diagnosed', from: condition.diagnosed_date || '—', to: formData.diagnosed_date || '—' });
    if ((formData.severity || null) !== (condition.severity || null)) changedFields.push({ label: 'Severity', from: condition.severity || '—', to: formData.severity || '—' });
    if ((formData.status || 'active') !== condition.status) changedFields.push({ label: 'Status', from: condition.status, to: formData.status || 'active' });
    if ((formData.notes || null) !== (condition.notes || null)) changedFields.push({ label: 'Notes', from: condition.notes || '—', to: formData.notes || '—' });
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={isEdit ? 'Edit Condition' : 'Add Condition'}>
      {showConfirm && isEdit ? (
        <div className="space-y-4">
          {changedFields.length === 0 ? (
            <p className="text-gray-500">No changes made.</p>
          ) : (
            <>
              <p className="text-sm text-gray-600">Confirm the following changes to <strong>{condition!.name}</strong>:</p>
              <div className="bg-gray-50 rounded-lg p-4 space-y-3 text-sm">
                {changedFields.map((field, i) => (
                  <div key={i}>
                    <span className="font-medium text-gray-700">{field.label}:</span>
                    <div className="ml-4 mt-0.5">
                      <span className="text-red-600 line-through">{field.from}</span>
                      <span className="mx-2 text-gray-400">&rarr;</span>
                      <span className="text-emerald-600">{field.to}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowConfirm(false)}>Go Back</Button>
            <Button onClick={handleConfirmEdit} disabled={updateMutation.isPending || changedFields.length === 0}>
              {updateMutation.isPending ? 'Saving...' : 'Confirm Changes'}
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input label="Condition Name *" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
          <MonthYearInput label="Diagnosed (Month/Year)" value={formData.diagnosed_date || null} onChange={(value) => setFormData({ ...formData, diagnosed_date: value })} />
          <Select label="Severity" value={formData.severity || ''} onChange={(e) => setFormData({ ...formData, severity: e.target.value || null })} options={[{ value: '', label: 'Select severity' }, { value: 'mild', label: 'Mild' }, { value: 'moderate', label: 'Moderate' }, { value: 'severe', label: 'Severe' }]} />
          <Select label="Status" value={formData.status || 'active'} onChange={(e) => setFormData({ ...formData, status: e.target.value })} options={[{ value: 'active', label: 'Active' }, { value: 'managed', label: 'Managed' }, { value: 'resolved', label: 'Resolved' }]} />
          <Textarea label="Notes" value={formData.notes || ''} onChange={(e) => setFormData({ ...formData, notes: e.target.value || null })} />
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="secondary" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving...' : isEdit ? 'Save Changes' : 'Add Condition'}</Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

// Medication Modal (supports create + edit)
function MedicationModal({ isOpen, onClose, profileId, medication }: { isOpen: boolean; onClose: () => void; profileId: string; medication?: Medication }) {
  const queryClient = useQueryClient();
  const isEdit = !!medication;
  const [formData, setFormData] = useState<MedicationCreate>({ name: '' });
  const [showConfirm, setShowConfirm] = useState(false);

  const resetKey = medication?.id ?? 'new';
  const [lastResetKey, setLastResetKey] = useState(resetKey);
  if (resetKey !== lastResetKey) {
    setLastResetKey(resetKey);
    if (medication) {
      setFormData({
        name: medication.name,
        dosage: medication.dosage,
        frequency: medication.frequency,
        prescribing_doctor: medication.prescribing_doctor,
        start_date: medication.start_date,
        end_date: medication.end_date,
        purpose: medication.purpose,
        side_effects: medication.side_effects,
      });
    } else {
      setFormData({ name: '' });
    }
    setShowConfirm(false);
  }

  const createMutation = useMutation({
    mutationFn: (data: MedicationCreate) => medications.create(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medications', profileId] });
      handleClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: MedicationCreate) => medications.update(profileId, medication!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medications', profileId] });
      handleClose();
    },
  });

  const mutation = isEdit ? updateMutation : createMutation;

  const handleClose = () => {
    setFormData({ name: '' });
    setShowConfirm(false);
    onClose();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isEdit) {
      setShowConfirm(true);
    } else {
      createMutation.mutate(formData);
    }
  };

  const changedFields: { label: string; from: string; to: string }[] = [];
  if (isEdit && medication) {
    if (formData.name !== medication.name) changedFields.push({ label: 'Name', from: medication.name, to: formData.name });
    if ((formData.dosage || null) !== (medication.dosage || null)) changedFields.push({ label: 'Dosage', from: medication.dosage || '—', to: formData.dosage || '—' });
    if ((formData.frequency || null) !== (medication.frequency || null)) changedFields.push({ label: 'Frequency', from: medication.frequency || '—', to: formData.frequency || '—' });
    if ((formData.prescribing_doctor || null) !== (medication.prescribing_doctor || null)) changedFields.push({ label: 'Prescribing Doctor', from: medication.prescribing_doctor || '—', to: formData.prescribing_doctor || '—' });
    if ((formData.start_date || null) !== (medication.start_date || null)) changedFields.push({ label: 'Start Date', from: medication.start_date || '—', to: formData.start_date || '—' });
    if ((formData.end_date || null) !== (medication.end_date || null)) changedFields.push({ label: 'End Date', from: medication.end_date || '—', to: formData.end_date || '—' });
    if ((formData.purpose || null) !== (medication.purpose || null)) changedFields.push({ label: 'Purpose', from: medication.purpose || '—', to: formData.purpose || '—' });
    if ((formData.side_effects || null) !== (medication.side_effects || null)) changedFields.push({ label: 'Side Effects', from: medication.side_effects || '—', to: formData.side_effects || '—' });
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={isEdit ? 'Edit Medication' : 'Add Medication'}>
      {showConfirm && isEdit ? (
        <div className="space-y-4">
          {changedFields.length === 0 ? (
            <p className="text-gray-500">No changes made.</p>
          ) : (
            <>
              <p className="text-sm text-gray-600">Confirm the following changes to <strong>{medication!.name}</strong>:</p>
              <div className="bg-gray-50 rounded-lg p-4 space-y-3 text-sm">
                {changedFields.map((field, i) => (
                  <div key={i}>
                    <span className="font-medium text-gray-700">{field.label}:</span>
                    <div className="ml-4 mt-0.5">
                      <span className="text-red-600 line-through">{field.from}</span>
                      <span className="mx-2 text-gray-400">&rarr;</span>
                      <span className="text-emerald-600">{field.to}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowConfirm(false)}>Go Back</Button>
            <Button onClick={() => updateMutation.mutate(formData)} disabled={updateMutation.isPending || changedFields.length === 0}>
              {updateMutation.isPending ? 'Saving...' : 'Confirm Changes'}
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input label="Medication Name *" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
          <Input label="Dosage" value={formData.dosage || ''} onChange={(e) => setFormData({ ...formData, dosage: e.target.value || null })} placeholder="e.g., 500mg" />
          <Input label="Frequency" value={formData.frequency || ''} onChange={(e) => setFormData({ ...formData, frequency: e.target.value || null })} placeholder="e.g., twice daily" />
          <Input label="Prescribing Doctor" value={formData.prescribing_doctor || ''} onChange={(e) => setFormData({ ...formData, prescribing_doctor: e.target.value || null })} />
          <DatePicker label="Start Date" value={formData.start_date || null} onChange={(value) => setFormData({ ...formData, start_date: value })} />
          <DatePicker label="End Date" value={formData.end_date || null} onChange={(value) => setFormData({ ...formData, end_date: value })} />
          <Textarea label="Purpose" value={formData.purpose || ''} onChange={(e) => setFormData({ ...formData, purpose: e.target.value || null })} />
          <Textarea label="Side Effects" value={formData.side_effects || ''} onChange={(e) => setFormData({ ...formData, side_effects: e.target.value || null })} />
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="secondary" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving...' : isEdit ? 'Save Changes' : 'Add Medication'}</Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

// Doctor Modal (supports create + edit)
function DoctorModal({ isOpen, onClose, profileId, doctor }: { isOpen: boolean; onClose: () => void; profileId: string; doctor?: Doctor }) {
  const queryClient = useQueryClient();
  const isEdit = !!doctor;
  const [formData, setFormData] = useState<DoctorCreate>({ name: '' });
  const [showConfirm, setShowConfirm] = useState(false);

  const resetKey = doctor?.id ?? 'new';
  const [lastResetKey, setLastResetKey] = useState(resetKey);
  if (resetKey !== lastResetKey) {
    setLastResetKey(resetKey);
    if (doctor) {
      setFormData({
        name: doctor.name,
        specialty: doctor.specialty,
        clinic: doctor.clinic,
        phone: doctor.phone,
        email: doctor.email,
        notes: doctor.notes,
        exclude_from_prep_context: doctor.exclude_from_prep_context,
      });
    } else {
      setFormData({ name: '' });
    }
    setShowConfirm(false);
  }

  const createMutation = useMutation({
    mutationFn: (data: DoctorCreate) => doctors.create(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['doctors', profileId] });
      handleClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: DoctorCreate) => doctors.update(profileId, doctor!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['doctors', profileId] });
      handleClose();
    },
  });

  const mutation = isEdit ? updateMutation : createMutation;

  const handleClose = () => {
    setFormData({ name: '' });
    setShowConfirm(false);
    onClose();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isEdit) {
      setShowConfirm(true);
    } else {
      createMutation.mutate(formData);
    }
  };

  const changedFields: { label: string; from: string; to: string }[] = [];
  if (isEdit && doctor) {
    if (formData.name !== doctor.name) changedFields.push({ label: 'Name', from: doctor.name, to: formData.name });
    if ((formData.specialty || null) !== (doctor.specialty || null)) changedFields.push({ label: 'Specialty', from: doctor.specialty || '—', to: formData.specialty || '—' });
    if ((formData.clinic || null) !== (doctor.clinic || null)) changedFields.push({ label: 'Clinic', from: doctor.clinic || '—', to: formData.clinic || '—' });
    if ((formData.phone || null) !== (doctor.phone || null)) changedFields.push({ label: 'Phone', from: doctor.phone || '—', to: formData.phone || '—' });
    if ((formData.email || null) !== (doctor.email || null)) changedFields.push({ label: 'Email', from: doctor.email || '—', to: formData.email || '—' });
    if ((formData.notes || null) !== (doctor.notes || null)) changedFields.push({ label: 'Notes', from: doctor.notes || '—', to: formData.notes || '—' });
    if ((formData.exclude_from_prep_context || false) !== doctor.exclude_from_prep_context) changedFields.push({ label: 'Exclude from prep', from: doctor.exclude_from_prep_context ? 'Yes' : 'No', to: formData.exclude_from_prep_context ? 'Yes' : 'No' });
  }

  // Stable checkbox ID for edit vs create mode
  const checkboxId = isEdit ? `exclude_from_prep_edit_${doctor?.id}` : 'exclude_from_prep';

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={isEdit ? 'Edit Doctor' : 'Add Doctor'}>
      {showConfirm && isEdit ? (
        <div className="space-y-4">
          {changedFields.length === 0 ? (
            <p className="text-gray-500">No changes made.</p>
          ) : (
            <>
              <p className="text-sm text-gray-600">Confirm the following changes to <strong>{doctor!.name}</strong>:</p>
              <div className="bg-gray-50 rounded-lg p-4 space-y-3 text-sm">
                {changedFields.map((field, i) => (
                  <div key={i}>
                    <span className="font-medium text-gray-700">{field.label}:</span>
                    <div className="ml-4 mt-0.5">
                      <span className="text-red-600 line-through">{field.from}</span>
                      <span className="mx-2 text-gray-400">&rarr;</span>
                      <span className="text-emerald-600">{field.to}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowConfirm(false)}>Go Back</Button>
            <Button onClick={() => updateMutation.mutate(formData)} disabled={updateMutation.isPending || changedFields.length === 0}>
              {updateMutation.isPending ? 'Saving...' : 'Confirm Changes'}
            </Button>
          </div>
        </div>
      ) : (
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
              id={checkboxId}
              checked={formData.exclude_from_prep_context || false}
              onChange={(e) => setFormData({ ...formData, exclude_from_prep_context: e.target.checked })}
              className="h-4 w-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
            />
            <label htmlFor={checkboxId} className="text-sm text-gray-700">
              Exclude from visit prep context (for sensitive specialties)
            </label>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="secondary" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving...' : isEdit ? 'Save Changes' : 'Add Doctor'}</Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

// Appointment Modal (supports create + edit)
function AppointmentModal({ isOpen, onClose, profileId, doctors, appointment }: { isOpen: boolean; onClose: () => void; profileId: string; doctors: Doctor[]; appointment?: Appointment }) {
  const queryClient = useQueryClient();
  const isEdit = !!appointment;

  // Convert ISO date to datetime-local format for the input
  const toLocalDatetime = (iso: string | null) => {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.toISOString().slice(0, 16);
  };

  const [formData, setFormData] = useState<AppointmentCreate>({
    doctor_id: doctors[0]?.id || '',
    scheduled_date: '',
    status: 'scheduled',
  });
  const [showConfirm, setShowConfirm] = useState(false);

  const resetKey = appointment?.id ?? 'new';
  const [lastResetKey, setLastResetKey] = useState(resetKey);
  if (resetKey !== lastResetKey) {
    setLastResetKey(resetKey);
    if (appointment) {
      setFormData({
        doctor_id: appointment.doctor_id || '',
        scheduled_date: toLocalDatetime(appointment.scheduled_date),
        purpose: appointment.purpose,
        status: appointment.status,
        prep_notes: appointment.prep_notes,
        visit_notes: appointment.visit_notes,
      });
    } else {
      setFormData({ doctor_id: doctors[0]?.id || '', scheduled_date: '', status: 'scheduled' });
    }
    setShowConfirm(false);
  }

  const createMutation = useMutation({
    mutationFn: (data: AppointmentCreate) => appointments.create(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments', profileId] });
      queryClient.invalidateQueries({ queryKey: ['pastDueAppointments', profileId] });
      queryClient.invalidateQueries({ queryKey: ['completedWithoutAvs', profileId] });
      handleClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: AppointmentCreate) => appointments.update(profileId, appointment!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments', profileId] });
      queryClient.invalidateQueries({ queryKey: ['pastDueAppointments', profileId] });
      queryClient.invalidateQueries({ queryKey: ['completedWithoutAvs', profileId] });
      handleClose();
    },
  });

  const mutation = isEdit ? updateMutation : createMutation;

  const handleClose = () => {
    setFormData({ doctor_id: doctors[0]?.id || '', scheduled_date: '', status: 'scheduled' });
    setShowConfirm(false);
    onClose();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isEdit) {
      setShowConfirm(true);
    } else {
      createMutation.mutate(formData);
    }
  };

  const getDoctorLabel = (id: string | null) => {
    if (!id) return '—';
    const d = doctors.find((doc) => doc.id === id);
    return d ? d.name : '—';
  };

  const changedFields: { label: string; from: string; to: string }[] = [];
  if (isEdit && appointment) {
    if ((formData.doctor_id || '') !== (appointment.doctor_id || '')) changedFields.push({ label: 'Doctor', from: getDoctorLabel(appointment.doctor_id), to: getDoctorLabel(formData.doctor_id || null) });
    if (formData.scheduled_date !== toLocalDatetime(appointment.scheduled_date)) changedFields.push({ label: 'Date & Time', from: appointment.scheduled_date ? new Date(appointment.scheduled_date).toLocaleString() : '—', to: formData.scheduled_date ? new Date(formData.scheduled_date).toLocaleString() : '—' });
    if ((formData.purpose || null) !== (appointment.purpose || null)) changedFields.push({ label: 'Purpose', from: appointment.purpose || '—', to: formData.purpose || '—' });
    if ((formData.status || 'scheduled') !== appointment.status) changedFields.push({ label: 'Status', from: appointment.status, to: formData.status || 'scheduled' });
    if ((formData.prep_notes || null) !== (appointment.prep_notes || null)) changedFields.push({ label: 'Pre-Visit Notes', from: appointment.prep_notes || '—', to: formData.prep_notes || '—' });
    if ((formData.visit_notes || null) !== (appointment.visit_notes || null)) changedFields.push({ label: 'Visit Notes', from: appointment.visit_notes || '—', to: formData.visit_notes || '—' });
  }

  const doctorOptions = [
    ...(isEdit ? [{ value: '', label: 'No doctor assigned' }] : []),
    ...doctors.map((d) => ({ value: d.id, label: `${d.name}${d.specialty ? ` (${d.specialty})` : ''}` })),
  ];

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={isEdit ? 'Edit Appointment' : 'Schedule Appointment'}>
      {showConfirm && isEdit ? (
        <div className="space-y-4">
          {changedFields.length === 0 ? (
            <p className="text-gray-500">No changes made.</p>
          ) : (
            <>
              <p className="text-sm text-gray-600">Confirm the following changes:</p>
              <div className="bg-gray-50 rounded-lg p-4 space-y-3 text-sm">
                {changedFields.map((field, i) => (
                  <div key={i}>
                    <span className="font-medium text-gray-700">{field.label}:</span>
                    <div className="ml-4 mt-0.5">
                      <span className="text-red-600 line-through">{field.from}</span>
                      <span className="mx-2 text-gray-400">&rarr;</span>
                      <span className="text-emerald-600">{field.to}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowConfirm(false)}>Go Back</Button>
            <Button onClick={() => updateMutation.mutate(formData)} disabled={updateMutation.isPending || changedFields.length === 0}>
              {updateMutation.isPending ? 'Saving...' : 'Confirm Changes'}
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Select
            label={isEdit ? 'Doctor' : 'Doctor *'}
            value={formData.doctor_id}
            onChange={(e) => setFormData({ ...formData, doctor_id: e.target.value })}
            options={doctorOptions}
          />
          <Input
            label="Date & Time *"
            type="datetime-local"
            value={formData.scheduled_date}
            onChange={(e) => setFormData({ ...formData, scheduled_date: e.target.value })}
            required
          />
          <Input label="Purpose" value={formData.purpose || ''} onChange={(e) => setFormData({ ...formData, purpose: e.target.value || null })} placeholder="e.g., Annual checkup" />
          {isEdit && (
            <Select label="Status" value={formData.status || 'scheduled'} onChange={(e) => setFormData({ ...formData, status: e.target.value })} options={[{ value: 'scheduled', label: 'Scheduled' }, { value: 'completed', label: 'Completed' }, { value: 'cancelled', label: 'Cancelled' }]} />
          )}
          <Textarea label="Pre-Visit Notes" value={formData.prep_notes || ''} onChange={(e) => setFormData({ ...formData, prep_notes: e.target.value || null })} placeholder="Questions or concerns to discuss" />
          {isEdit && (
            <Textarea label="Visit Notes" value={formData.visit_notes || ''} onChange={(e) => setFormData({ ...formData, visit_notes: e.target.value || null })} placeholder="Notes from the visit" />
          )}
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="secondary" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving...' : isEdit ? 'Save Changes' : 'Schedule'}</Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
