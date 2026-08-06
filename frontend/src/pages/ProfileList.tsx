import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { profiles, downloadDeletedProfileExport } from '../api/client';
import { formatDateString } from '../utils/date';
import { Card, CardContent } from '../components/Card';
import { Button } from '../components/Button';
import { Modal } from '../components/Modal';
import { Input, DatePicker } from '../components/Input';
import { SOFT_DELETE_RETENTION_DAYS } from '../constants';
import type { HealthProfileCreate } from '../types';

export default function ProfileList() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [showDeleted, setShowDeleted] = useState(false);
  const [formData, setFormData] = useState<HealthProfileCreate>({ name: '' });
  const [exportingId, setExportingId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: profileList, isLoading } = useQuery({
    queryKey: ['profiles'],
    queryFn: profiles.list,
  });

  // Soft-deleted profiles still inside their recovery window (issue #50).
  // Always fetched rather than only on expand, so the "Recently deleted (n)"
  // toggle can be hidden entirely when there's nothing to recover.
  const { data: deletedList } = useQuery({
    queryKey: ['profiles', 'deleted'],
    queryFn: profiles.listDeleted,
  });

  const createMutation = useMutation({
    mutationFn: profiles.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      setIsModalOpen(false);
      setFormData({ name: '' });
    },
  });

  const restoreMutation = useMutation({
    mutationFn: profiles.restore,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  const handleExportDeleted = async (profileId: string) => {
    setExportingId(profileId);
    try {
      await downloadDeletedProfileExport(profileId);
    } finally {
      setExportingId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Health Profiles</h1>
          <p className="text-gray-600 mt-1">Manage your health profiles and medical information</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>+ New Profile</Button>
      </div>

      {profileList?.length === 0 ? (
        <Card>
          <CardContent className="text-center py-12">
            <div className="text-gray-400 text-5xl mb-4">👤</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No profiles yet</h3>
            <p className="text-gray-600 mb-4">Create your first health profile to get started</p>
            <Button onClick={() => setIsModalOpen(true)}>Create Profile</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {profileList?.map((profile) => (
            <Link key={profile.id} to={`/profiles/${profile.id}`}>
              <Card className="hover:border-brand-teal-bright/40 hover:shadow-md transition-all cursor-pointer h-full">
                <CardContent>
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 bg-brand-teal-bright/15 rounded-full flex items-center justify-center flex-shrink-0">
                      <span className="text-brand-teal font-semibold text-lg">
                        {profile.name.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold text-gray-900 truncate">{profile.name}</h3>
                      {profile.blood_type && (
                        <p className="text-sm text-gray-500">Blood Type: {profile.blood_type}</p>
                      )}
                      {profile.date_of_birth && (
                        <p className="text-sm text-gray-500">
                          DOB: {formatDateString(profile.date_of_birth)}
                        </p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {deletedList && deletedList.length > 0 && (
        <div className="pt-2">
          <button
            type="button"
            onClick={() => setShowDeleted((open) => !open)}
            className="text-sm font-medium text-gray-500 hover:text-gray-700"
          >
            {showDeleted ? '▾' : '▸'} Recently deleted ({deletedList.length})
          </button>

          {showDeleted && (
            <div className="mt-3 space-y-2">
              <p className="text-sm text-gray-500">
                Deleted profiles are kept for {SOFT_DELETE_RETENTION_DAYS} days, then permanently
                deleted. Restore one to bring it back with all of its data.
              </p>
              {deletedList.map((profile) => (
                <Card key={profile.id}>
                  <CardContent className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <h3 className="font-medium text-gray-900 truncate">{profile.name}</h3>
                      <p className="text-sm text-gray-500">
                        Deleted {formatDateString(profile.deleted_at)} ·{' '}
                        {profile.days_remaining === 0
                          ? 'less than a day left'
                          : `${profile.days_remaining} day${profile.days_remaining === 1 ? '' : 's'} left`}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <Button
                        variant="secondary"
                        onClick={() => handleExportDeleted(profile.id)}
                        disabled={exportingId === profile.id}
                      >
                        {exportingId === profile.id ? 'Exporting...' : 'Export'}
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => restoreMutation.mutate(profile.id)}
                        disabled={restoreMutation.isPending}
                      >
                        Restore
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Create Health Profile">
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Name *"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Enter full name"
            required
          />
          <DatePicker
            label="Date of Birth"
            value={formData.date_of_birth || null}
            onChange={(value) => setFormData({ ...formData, date_of_birth: value })}
          />
          <Input
            label="Blood Type"
            value={formData.blood_type || ''}
            onChange={(e) => setFormData({ ...formData, blood_type: e.target.value || null })}
            placeholder="e.g., O+, A-, B+"
          />
          <Input
            label="Allergies"
            value={formData.allergies || ''}
            onChange={(e) => setFormData({ ...formData, allergies: e.target.value || null })}
            placeholder="e.g., Penicillin, Peanuts"
          />
          <Input
            label="Emergency Contact Name"
            value={formData.emergency_contact_name || ''}
            onChange={(e) => setFormData({ ...formData, emergency_contact_name: e.target.value || null })}
          />
          <Input
            label="Emergency Contact Phone"
            value={formData.emergency_contact_phone || ''}
            onChange={(e) => setFormData({ ...formData, emergency_contact_phone: e.target.value || null })}
            placeholder="+1-555-123-4567"
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="secondary" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create Profile'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
