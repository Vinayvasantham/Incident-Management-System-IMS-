import type { Incident, IncidentSummary } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || response.statusText);
  }

  return response.json() as Promise<T>;
}

export function listIncidents(): Promise<IncidentSummary[]> {
  return request('/incidents');
}

export function getIncident(id: string): Promise<Incident> {
  return request(`/incidents/${id}`);
}

export function submitRca(id: string, payload: {
  start_time: string;
  end_time: string;
  root_cause_category: string;
  fix_applied: string;
  prevention_steps: string;
}): Promise<Incident> {
  return request(`/incidents/${id}/rca`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function ingestSample(payload: {
  component_id: string;
  component_type: string;
  message: string;
  severity_hint?: string;
  source?: string;
}): Promise<{ accepted: boolean; signal_id: string }> {
  return request('/ingest', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
