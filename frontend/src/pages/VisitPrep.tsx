import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { profiles, appointments, doctors, visitPrep } from '../api/client';
import { Card, CardHeader, CardContent } from '../components/Card';
import { Button } from '../components/Button';
import { Textarea } from '../components/Input';

export default function VisitPrep() {
  const { profileId, appointmentId } = useParams<{ profileId: string; appointmentId: string }>();
  const queryClient = useQueryClient();
  const [additionalConcerns, setAdditionalConcerns] = useState('');

  // Queries
  const { data: profile } = useQuery({
    queryKey: ['profile', profileId],
    queryFn: () => profiles.get(profileId!),
    enabled: !!profileId,
  });

  const { data: appointment } = useQuery({
    queryKey: ['appointment', profileId, appointmentId],
    queryFn: () => appointments.get(profileId!, appointmentId!),
    enabled: !!profileId && !!appointmentId,
  });

  const { data: doctorList } = useQuery({
    queryKey: ['doctors', profileId],
    queryFn: () => doctors.list(profileId!),
    enabled: !!profileId,
  });

  const { data: prep } = useQuery({
    queryKey: ['visitPrep', appointmentId],
    queryFn: () => visitPrep.get(appointmentId!),
    enabled: !!appointmentId,
    retry: false,
  });

  // Generate mutation
  const generateMutation = useMutation({
    mutationFn: () => visitPrep.prepare(appointmentId!, additionalConcerns || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['visitPrep', appointmentId] });
    },
  });

  const doctor = doctorList?.find((d) => d.id === appointment?.doctor_id);

  if (!profile || !appointment) {
    return <div className="text-center py-12 text-gray-500">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to={`/profiles/${profileId}`} className="text-gray-400 hover:text-gray-600">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">Visit Preparation</h1>
          <p className="text-gray-500">
            {doctor?.name} • {new Date(appointment.scheduled_date).toLocaleDateString()}
          </p>
        </div>
      </div>

      {/* Appointment Info */}
      <Card>
        <CardHeader>
          <h3 className="font-semibold text-gray-900">Appointment Details</h3>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-sm text-gray-500">Doctor</p>
              <p className="font-medium">{doctor?.name || 'Unknown'}</p>
              {doctor?.specialty && <p className="text-sm text-emerald-600">{doctor.specialty}</p>}
            </div>
            <div>
              <p className="text-sm text-gray-500">Date & Time</p>
              <p className="font-medium">{new Date(appointment.scheduled_date).toLocaleString()}</p>
            </div>
            {appointment.purpose && (
              <div className="md:col-span-2">
                <p className="text-sm text-gray-500">Purpose</p>
                <p className="font-medium">{appointment.purpose}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Generate Section */}
      {!prep && (
        <Card>
          <CardHeader>
            <h3 className="font-semibold text-gray-900">Generate AI-Powered Questions</h3>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-gray-600">
              Our AI will analyze your health profile, conditions, and medications to generate
              personalized questions for your doctor visit.
            </p>
            <Textarea
              label="Additional Concerns (optional)"
              value={additionalConcerns}
              onChange={(e) => setAdditionalConcerns(e.target.value)}
              placeholder="Any specific concerns or symptoms you'd like to discuss?"
            />
            <Button
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
              className="w-full"
            >
              {generateMutation.isPending ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Generating Questions...
                </span>
              ) : (
                '✨ Generate Questions with AI'
              )}
            </Button>
            {generateMutation.isError && (
              <p className="text-sm text-red-600">
                Failed to generate questions. Please check your API key is configured.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Questions Display */}
      {prep && (
        <div className="space-y-6">
          {/* Context Summary */}
          {prep.context_summary && (
            <Card>
              <CardHeader>
                <h3 className="font-semibold text-gray-900">Health Context Summary</h3>
              </CardHeader>
              <CardContent>
                <p className="text-gray-700">{prep.context_summary}</p>
              </CardContent>
            </Card>
          )}

          {/* Questions by Category */}
          {prep.generated_questions && Object.keys(prep.generated_questions).length > 0 && (
            <div className="space-y-4">
              <h3 className="font-semibold text-gray-900 text-lg">Questions to Ask Your Doctor</h3>
              {Object.entries(prep.generated_questions).map(([category, questions]) => (
                <Card key={category}>
                  <CardHeader className="bg-gray-50">
                    <h4 className="font-medium text-gray-900">{category}</h4>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-3">
                      {(questions as string[]).map((question, idx) => (
                        <li key={idx} className="flex gap-3">
                          <span className="flex-shrink-0 w-6 h-6 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center text-sm font-medium">
                            {idx + 1}
                          </span>
                          <span className="text-gray-700">{question}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Regenerate Button */}
          <div className="flex justify-center">
            <Button
              variant="secondary"
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
            >
              {generateMutation.isPending ? 'Regenerating...' : '🔄 Regenerate Questions'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
