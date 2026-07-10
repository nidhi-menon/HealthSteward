import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { appSettings } from '../api/client';
import { Card, CardContent, CardHeader } from '../components/Card';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import type { AppSettingsUpdate, LlmProvider } from '../types';

const PROVIDER_OPTIONS: { value: LlmProvider; label: string; description: string }[] = [
  {
    value: 'ollama',
    label: 'Ollama (local)',
    description: 'Runs entirely on this machine — nothing leaves your device. Default.',
  },
  {
    value: 'claude',
    label: 'Claude API',
    description: 'Anonymized data is sent to Anthropic for higher-quality visit prep.',
  },
  {
    value: 'custom',
    label: 'Custom (OpenAI-compatible)',
    description: 'Point at any OpenAI-compatible endpoint — OpenAI, OpenRouter, Groq, a self-hosted server, etc.',
  },
];

export default function Settings() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: appSettings.get,
  });

  const [form, setForm] = useState<AppSettingsUpdate>({});
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setForm({
        llm_provider: data.llm_provider,
        anthropic_model: data.anthropic_model,
        ollama_base_url: data.ollama_base_url,
        ollama_model: data.ollama_model,
        custom_llm_base_url: data.custom_llm_base_url ?? undefined,
        custom_llm_model: data.custom_llm_model ?? undefined,
      });
    }
  }, [data]);

  const updateMutation = useMutation({
    mutationFn: appSettings.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setSavedMessage('Saved.');
      setTimeout(() => setSavedMessage(null), 3000);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Drop empty-string secret fields so we don't overwrite a saved key
    // with blank just because the masked placeholder wasn't touched.
    const payload = { ...form };
    if (!payload.anthropic_api_key) delete payload.anthropic_api_key;
    if (!payload.custom_llm_api_key) delete payload.custom_llm_api_key;
    updateMutation.mutate(payload);
  };

  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  const provider = form.llm_provider ?? data.llm_provider;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">
          Choose which AI backend generates visit prep questions. Ollama runs locally by default —
          switching to Claude or a custom provider sends anonymized data off-device.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-gray-900">LLM Provider</h2>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              {PROVIDER_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    provider === opt.value
                      ? 'border-emerald-500 bg-emerald-50'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="llm_provider"
                    value={opt.value}
                    checked={provider === opt.value}
                    onChange={() => setForm((f) => ({ ...f, llm_provider: opt.value }))}
                    className="mt-1"
                  />
                  <div>
                    <div className="font-medium text-gray-900">{opt.label}</div>
                    <div className="text-sm text-gray-600">{opt.description}</div>
                  </div>
                </label>
              ))}
            </div>
          </CardContent>
        </Card>

        {provider === 'claude' && (
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900">Claude API</h2>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input
                label="API key"
                type="password"
                placeholder={data.anthropic_api_key ?? 'sk-ant-...'}
                value={form.anthropic_api_key ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, anthropic_api_key: e.target.value }))}
              />
              <Input
                label="Model"
                value={form.anthropic_model ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, anthropic_model: e.target.value }))}
              />
            </CardContent>
          </Card>
        )}

        {provider === 'ollama' && (
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900">Ollama</h2>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input
                label="Base URL"
                value={form.ollama_base_url ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, ollama_base_url: e.target.value }))}
              />
              <Input
                label="Model"
                value={form.ollama_model ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, ollama_model: e.target.value }))}
              />
            </CardContent>
          </Card>
        )}

        {provider === 'custom' && (
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900">Custom (OpenAI-compatible)</h2>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input
                label="Base URL"
                placeholder="https://api.example.com/v1"
                value={form.custom_llm_base_url ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, custom_llm_base_url: e.target.value }))}
              />
              <Input
                label="API key (optional)"
                type="password"
                placeholder={data.custom_llm_api_key ?? 'leave blank if not required'}
                value={form.custom_llm_api_key ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, custom_llm_api_key: e.target.value }))}
              />
              <Input
                label="Model"
                value={form.custom_llm_model ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, custom_llm_model: e.target.value }))}
              />
            </CardContent>
          </Card>
        )}

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={updateMutation.isPending}>
            {updateMutation.isPending ? 'Saving...' : 'Save'}
          </Button>
          {savedMessage && <span className="text-sm text-emerald-600">{savedMessage}</span>}
          {updateMutation.isError && (
            <span className="text-sm text-red-600">{(updateMutation.error as Error).message}</span>
          )}
        </div>
      </form>
    </div>
  );
}
