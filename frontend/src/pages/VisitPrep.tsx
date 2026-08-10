import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { profiles, appointments, doctors, visitPrep } from '../api/client';
import { Card, CardHeader, CardContent } from '../components/Card';
import { Button } from '../components/Button';
import { Textarea } from '../components/Input';
import { VisitChecklistCard } from '../components/VisitChecklistCard';
import type { VisitPrepUpdate } from '../types';

export default function VisitPrep() {
  const { profileId, appointmentId } = useParams<{ profileId: string; appointmentId: string }>();
  const queryClient = useQueryClient();
  const [additionalConcerns, setAdditionalConcerns] = useState('');
  const [visitNotes, setVisitNotes] = useState('');
  const [isEditingNotes, setIsEditingNotes] = useState(false);

  // Issue #14: in-place editing of generated questions. Each category's
  // questions are edited as one newline-delimited textarea — one line per
  // question — which covers all three things the issue asks for (reword a
  // question, add one of your own, drop one that doesn't apply) without
  // needing per-question widgets or a change to generated_questions' shape.
  const [isEditingPrep, setIsEditingPrep] = useState(false);
  const [draftQuestions, setDraftQuestions] = useState<Record<string, string>>({});
  const [draftSummary, setDraftSummary] = useState('');

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

  // Issue #54: prior generations, kept because "Regenerate Questions" used to
  // destroy the previous output outright. Read-only on purpose — a restore
  // action would re-raise the same overwrite question one level up, and being
  // able to see and copy the old questions already removes the data loss.
  const { data: prepVersions } = useQuery({
    queryKey: ['visitPrepVersions', appointmentId],
    queryFn: () => visitPrep.versions(appointmentId!),
    enabled: !!appointmentId && !!prep,
  });
  const [showVersions, setShowVersions] = useState(false);

  // Initialize visit notes from appointment
  useEffect(() => {
    if (appointment?.visit_notes) {
      setVisitNotes(appointment.visit_notes);
    }
  }, [appointment?.visit_notes]);

  // Generate mutation
  const generateMutation = useMutation({
    mutationFn: () => visitPrep.prepare(appointmentId!, additionalConcerns || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['visitPrep', appointmentId] });
      queryClient.invalidateQueries({ queryKey: ['upcomingWithoutPrep', profileId] });
      // Regenerating is exactly what adds a version, so the history list is
      // stale the moment this succeeds.
      queryClient.invalidateQueries({ queryKey: ['visitPrepVersions', appointmentId] });
    },
  });

  // Save edited prep (issue #14). Regenerate still replaces everything —
  // this only persists what the user changed by hand.
  const updatePrepMutation = useMutation({
    mutationFn: (data: VisitPrepUpdate) => visitPrep.update(appointmentId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['visitPrep', appointmentId] });
      setIsEditingPrep(false);
    },
  });

  const startEditingPrep = () => {
    const questions = prep?.generated_questions ?? {};
    setDraftQuestions(
      Object.fromEntries(
        Object.entries(questions).map(([category, list]) => [category, list.join('\n')])
      )
    );
    setDraftSummary(prep?.context_summary ?? '');
    setIsEditingPrep(true);
  };

  const saveEditedPrep = () => {
    // Blank lines are how a question gets deleted, so drop them. A category
    // left entirely empty is dropped too, rather than persisting a heading with
    // nothing under it — clearing a category is a legitimate way to remove one.
    const cleaned: Record<string, string[]> = {};
    for (const [category, text] of Object.entries(draftQuestions)) {
      const items = text
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
      if (items.length > 0) {
        cleaned[category] = items;
      }
    }
    updatePrepMutation.mutate({
      generated_questions: cleaned,
      context_summary: draftSummary,
    });
  };

  // Update appointment mutation (for visit notes)
  const updateAppointmentMutation = useMutation({
    mutationFn: (data: { visit_notes?: string; status?: string }) =>
      appointments.update(profileId!, appointmentId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointment', profileId, appointmentId] });
      queryClient.invalidateQueries({ queryKey: ['appointments', profileId] });
      queryClient.invalidateQueries({ queryKey: ['pastDueAppointments', profileId] });
      queryClient.invalidateQueries({ queryKey: ['completedWithoutAvs', profileId] });
      setIsEditingNotes(false);
    },
  });

  const doctor = doctorList?.find((d) => d.id === appointment?.doctor_id);

  if (!profile || !appointment) {
    return <div className="text-center py-12 text-gray-500">Loading...</div>;
  }

  const isCompleted = appointment.status === 'completed';
  const isPast = new Date(appointment.scheduled_date) < new Date();

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
          <h1 className="text-2xl font-bold text-gray-900">
            {isCompleted ? 'Visit Summary' : 'Visit Preparation'}
          </h1>
          <p className="text-gray-500">
            {doctor?.name} • {new Date(appointment.scheduled_date).toLocaleDateString()}
          </p>
        </div>
        {isPast && !isCompleted && (
          <Button
            size="sm"
            onClick={() => updateAppointmentMutation.mutate({ status: 'completed' })}
            disabled={updateAppointmentMutation.isPending}
          >
            Mark as Completed
          </Button>
        )}
      </div>

      {/* Appointment Info */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <h3 className="font-semibold text-gray-900">Appointment Details</h3>
            <span className={`px-2 py-0.5 rounded-full text-xs ${
              appointment.status === 'scheduled' ? 'bg-blue-100 text-blue-700' :
              appointment.status === 'completed' ? 'bg-green-100 text-green-700' :
              'bg-gray-100 text-gray-700'
            }`}>
              {appointment.status}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-sm text-gray-500">Doctor</p>
              <p className="font-medium">{doctor?.name || 'Unknown'}</p>
              {doctor?.specialty && <p className="text-sm text-brand-teal-bright">{doctor.specialty}</p>}
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

      {/* What to bring (issue #110) — pre-visit only; it has no use afterwards */}
      {!isCompleted && appointmentId && (
        <VisitChecklistCard profileId={profileId!} appointmentId={appointmentId} />
      )}

      {/* Pre-visit Notes */}
      {appointment.prep_notes && (
        <Card>
          <CardHeader>
            <h3 className="font-semibold text-gray-900">Pre-Visit Notes</h3>
          </CardHeader>
          <CardContent>
            <p className="text-gray-700">{appointment.prep_notes}</p>
          </CardContent>
        </Card>
      )}

      {/* Generate Section - Only show if not completed */}
      {!prep && !isCompleted && (
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
                'Generate Questions with AI'
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
          {prep.used_fallback && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800 flex items-start gap-2">
              <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
              </svg>
              <span>
                Couldn't reach your configured AI backend, so these are generic default questions,
                not personalized to your health profile. Check your{' '}
                <Link to="/settings" className="underline font-medium">Settings</Link> and regenerate.
              </span>
            </div>
          )}

          {/* Context Summary */}
          {(prep.context_summary || isEditingPrep) && (
            <Card>
              <CardHeader>
                <h3 className="font-semibold text-gray-900">Health Context Summary</h3>
              </CardHeader>
              <CardContent>
                {isEditingPrep ? (
                  <Textarea
                    label=""
                    value={draftSummary}
                    onChange={(e) => setDraftSummary(e.target.value)}
                    placeholder="Summary of the health context behind these questions..."
                    rows={4}
                  />
                ) : (
                  <p className="text-gray-700">{prep.context_summary}</p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Questions by Category */}
          {prep.generated_questions && Object.keys(prep.generated_questions).length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-900 text-lg">Questions to Ask Your Doctor</h3>
                {!isCompleted && !isEditingPrep && (
                  <Button size="sm" variant="secondary" onClick={startEditingPrep}>
                    Edit
                  </Button>
                )}
              </div>

              {isEditingPrep && (
                <p className="text-sm text-gray-600">
                  One question per line. Delete a line to remove that question, or add a line to
                  ask something of your own. Clearing a whole category removes it.
                </p>
              )}

              {Object.entries(prep.generated_questions).map(([category, questions]) => (
                <Card key={category}>
                  <CardHeader className="bg-gray-50">
                    <h4 className="font-medium text-gray-900">{category}</h4>
                  </CardHeader>
                  <CardContent>
                    {isEditingPrep ? (
                      <Textarea
                        label=""
                        value={draftQuestions[category] ?? ''}
                        onChange={(e) =>
                          setDraftQuestions((d) => ({ ...d, [category]: e.target.value }))
                        }
                        rows={Math.max(3, (draftQuestions[category] ?? '').split('\n').length + 1)}
                      />
                    ) : (
                      <ul className="space-y-3">
                        {(questions as string[]).map((question, idx) => (
                          <li key={idx} className="flex gap-3">
                            <span className="flex-shrink-0 w-6 h-6 bg-brand-teal-bright/15 text-brand-teal rounded-full flex items-center justify-center text-sm font-medium">
                              {idx + 1}
                            </span>
                            <span className="text-gray-700">{question}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Save/Cancel while editing, Regenerate otherwise */}
          {!isCompleted && (
            <div className="flex justify-center gap-3">
              {isEditingPrep ? (
                <>
                  <Button onClick={saveEditedPrep} disabled={updatePrepMutation.isPending}>
                    {updatePrepMutation.isPending ? 'Saving...' : 'Save Changes'}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setIsEditingPrep(false)}
                    disabled={updatePrepMutation.isPending}
                  >
                    Cancel
                  </Button>
                </>
              ) : (
                <Button
                  variant="secondary"
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                >
                  {generateMutation.isPending ? 'Regenerating...' : 'Regenerate Questions'}
                </Button>
              )}
            </div>
          )}

          {updatePrepMutation.isError && (
            <p className="text-sm text-red-600 text-center">
              Failed to save your changes. Please try again.
            </p>
          )}

          {/* Previous versions (issue #54). Hidden entirely when there is no
              history, so a prep that has never been regenerated looks exactly
              as it did before. Read-only: no restore, no diff. */}
          {prepVersions && prepVersions.length > 0 && (
            <div className="border-t border-gray-200 pt-4">
              <button
                type="button"
                onClick={() => setShowVersions((v) => !v)}
                className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
                aria-expanded={showVersions}
              >
                <svg
                  className={`w-4 h-4 transition-transform ${showVersions ? 'rotate-90' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Previous versions ({prepVersions.length})
              </button>

              {showVersions && (
                <div className="mt-3 space-y-3">
                  <p className="text-sm text-gray-600">
                    Earlier questions for this visit, kept from before each time you regenerated.
                    They're shown for reference only — copy anything you still want into the
                    current list above.
                  </p>
                  {prepVersions.map((version) => (
                    <Card key={version.id}>
                      <CardHeader className="bg-gray-50">
                        <div className="flex items-baseline justify-between gap-3">
                          <h4 className="font-medium text-gray-900 text-sm">
                            Version {version.version_number}
                          </h4>
                          <span className="text-xs text-gray-400">
                            {version.content_updated_at
                              ? `written ${new Date(version.content_updated_at).toLocaleString()}`
                              : `replaced ${new Date(version.created_at).toLocaleString()}`}
                          </span>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {version.used_fallback && (
                          <p className="text-xs text-amber-700">
                            These were generic default questions — the AI backend was
                            unreachable when this version was generated.
                          </p>
                        )}
                        {version.context_summary && (
                          <p className="text-sm text-gray-600 italic">{version.context_summary}</p>
                        )}
                        {version.generated_questions &&
                          Object.entries(version.generated_questions).map(([category, questions]) => (
                            <div key={category}>
                              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                                {category}
                              </p>
                              <ul className="mt-1 space-y-1">
                                {questions.map((question, idx) => (
                                  <li key={idx} className="flex gap-2 text-sm text-gray-700">
                                    <span aria-hidden="true" className="text-gray-400">
                                      •
                                    </span>
                                    <span>{question}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ))}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Visit Notes Section - Show for completed or past appointments */}
      {(isCompleted || isPast) && (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <h3 className="font-semibold text-gray-900">Visit Notes</h3>
              {appointment.visit_notes && !isEditingNotes && (
                <Button size="sm" variant="secondary" onClick={() => setIsEditingNotes(true)}>
                  Edit
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {isEditingNotes || !appointment.visit_notes ? (
              <>
                <p className="text-gray-600 text-sm">
                  Record notes from your visit: what was discussed, recommendations, follow-ups, etc.
                </p>
                <Textarea
                  label=""
                  value={visitNotes}
                  onChange={(e) => setVisitNotes(e.target.value)}
                  placeholder="Enter notes from your visit..."
                  rows={6}
                />
                <div className="flex gap-3">
                  <Button
                    onClick={() => updateAppointmentMutation.mutate({ visit_notes: visitNotes })}
                    disabled={updateAppointmentMutation.isPending}
                  >
                    {updateAppointmentMutation.isPending ? 'Saving...' : 'Save Visit Notes'}
                  </Button>
                  {appointment.visit_notes && (
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setVisitNotes(appointment.visit_notes || '');
                        setIsEditingNotes(false);
                      }}
                    >
                      Cancel
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <div>
                <p className="text-gray-700 whitespace-pre-wrap">{appointment.visit_notes}</p>
                {appointment.visit_notes_updated_at && (
                  <p className="text-xs text-gray-400 mt-2">
                    Last updated: {new Date(appointment.visit_notes_updated_at).toLocaleString()}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
