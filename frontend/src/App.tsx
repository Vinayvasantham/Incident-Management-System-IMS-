import { useEffect, useMemo, useState } from 'react';
import { getIncident, ingestSample, listIncidents, submitRca } from './lib/api';
import type { Incident, IncidentSummary } from './types';

const SEVERITY_ORDER = { P0: 0, P1: 1, P2: 2, P3: 3 } as const;
const RCA_OPTIONS = [
  'Configuration Drift',
  'Upstream Dependency',
  'Cache Invalidation',
  'Capacity Exhaustion',
  'Network Partition',
  'Code Regression',
  'Human Error',
];

function formatTime(value: string): string {
  return new Date(value).toLocaleString();
}

function toDatetimeLocalValue(value: string): string {
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function sortIncidents(items: IncidentSummary[]): IncidentSummary[] {
  return [...items].sort((left, right) => {
    const severityDelta = SEVERITY_ORDER[left.severity] - SEVERITY_ORDER[right.severity];
    if (severityDelta !== 0) return severityDelta;
    return new Date(right.last_signal_at).getTime() - new Date(left.last_signal_at).getTime();
  });
}

export default function App() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [rcaForm, setRcaForm] = useState(() => ({
    start_time: new Date().toISOString().slice(0, 16),
    end_time: new Date().toISOString().slice(0, 16),
    root_cause_category: RCA_OPTIONS[0],
    fix_applied: '',
    prevention_steps: '',
  }));

  async function refreshList() {
    try {
      const data = await listIncidents();
      const sorted = sortIncidents(data);
      setIncidents(sorted);
      if (!selectedId && sorted.length > 0) {
        setSelectedId(sorted[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to fetch incidents');
    }
  }

  useEffect(() => {
    void refreshList();
    const interval = window.setInterval(() => void refreshList(), 5000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    void getIncident(selectedId)
      .then((incident) => {
        if (active) {
          setSelectedIncident(incident);
          setRcaForm((current) => ({
            ...current,
            start_time: incident.rca?.start_time ? toDatetimeLocalValue(incident.rca.start_time) : current.start_time,
            end_time: incident.rca?.end_time ? toDatetimeLocalValue(incident.rca.end_time) : current.end_time,
          }));
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to fetch incident'));
    return () => {
      active = false;
    };
  }, [selectedId]);

  const activeCount = useMemo(() => incidents.filter((incident) => incident.status !== 'CLOSED').length, [incidents]);

  async function seedDemo() {
    setStatus('Seeding sample failures...');
    setError('');
    try {
      await ingestSample({ component_id: 'RDBMS_PRIMARY', component_type: 'RDBMS', message: 'Primary database unavailable', source: 'sample-stream' });
      await ingestSample({ component_id: 'MCP_HOST_02', component_type: 'MCP_HOST', message: 'MCP host failed health check', source: 'sample-stream' });
      await refreshList();
      setStatus('Sample failures submitted');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to submit sample failures');
    }
  }

  async function closeIncident() {
    if (!selectedId) return;
    setLoading(true);
    setError('');
    try {
      const updated = await submitRca(selectedId, {
        start_time: new Date(rcaForm.start_time).toISOString(),
        end_time: new Date(rcaForm.end_time).toISOString(),
        root_cause_category: rcaForm.root_cause_category,
        fix_applied: rcaForm.fix_applied,
        prevention_steps: rcaForm.prevention_steps,
      });
      setSelectedIncident(updated);
      await refreshList();
      setStatus(`Incident closed with MTTR ${updated.mttr_minutes ?? 0} minutes`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to close incident');
    } finally {
      setLoading(false);
    }
  }

  const selectedSummary = incidents.find((incident) => incident.id === selectedId) ?? null;

  return (
    <div className="shell">
      <aside className="hero-panel">
        <div className="eyebrow">Mission-Critical IMS</div>
        <h1>Incident command for noisy distributed systems.</h1>
        <p>
          Async ingestion, burst buffering, debounced incident creation, and mandatory RCA closure in one workflow.
        </p>
        <div className="hero-actions">
          <button type="button" onClick={seedDemo}>Seed failure stream</button>
          <button type="button" className="secondary" onClick={() => void refreshList()}>Refresh</button>
        </div>
        <div className="metrics-grid">
          <div className="metric">
            <strong>{activeCount}</strong>
            <span>Active incidents</span>
          </div>
          <div className="metric">
            <strong>{incidents[0]?.severity ?? 'P3'}</strong>
            <span>Highest severity</span>
          </div>
          <div className="metric">
            <strong>{selectedIncident?.signal_count ?? 0}</strong>
            <span>Signals in focus</span>
          </div>
        </div>
        {status && <div className="notice success">{status}</div>}
        {error && <div className="notice error">{error}</div>}
      </aside>

      <main className="workspace">
        <section className="card incident-list-card">
          <div className="section-header">
            <h2>Live Feed</h2>
            <span>Sorted by severity then recency</span>
          </div>
          <div className="incident-list">
            {incidents.length === 0 ? (
              <p className="empty-state">No incidents yet. Seed a sample failure or ingest signals.</p>
            ) : (
              incidents.map((incident) => (
                <button
                  type="button"
                  className={`incident-row ${incident.id === selectedId ? 'selected' : ''}`}
                  key={incident.id}
                  onClick={() => setSelectedId(incident.id)}
                >
                  <div>
                    <strong>{incident.component_id}</strong>
                    <p>{incident.alert_type}</p>
                  </div>
                  <div className="row-meta">
                    <span className={`severity severity-${incident.severity.toLowerCase()}`}>{incident.severity}</span>
                    <span>{incident.signal_count} signals</span>
                    <span>{incident.status}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </section>

        <section className="card detail-grid">
          <div className="detail-pane">
            <div className="section-header">
              <h2>Incident Detail</h2>
              <span>{selectedSummary?.component_type ?? 'Select an incident'}</span>
            </div>
            {selectedSummary ? (
              <>
                <div className="detail-cards">
                  <div className="detail-card"><span>Status</span><strong>{selectedSummary.status}</strong></div>
                  <div className="detail-card"><span>First signal</span><strong>{formatTime(selectedSummary.first_signal_at)}</strong></div>
                  <div className="detail-card"><span>Last signal</span><strong>{formatTime(selectedSummary.last_signal_at)}</strong></div>
                  <div className="detail-card"><span>MTTR</span><strong>{selectedSummary.mttr_minutes ?? 'Pending'}</strong></div>
                </div>
                <div className="signals-panel">
                  <h3>Raw Signals</h3>
                  <div className="signals-list">
                    {(selectedIncident?.signals ?? []).map((signal, index) => (
                      <pre key={`${selectedSummary.id}-${index}`}>{JSON.stringify(signal, null, 2)}</pre>
                    ))}
                    {(selectedIncident?.signals ?? []).length === 0 && <p className="empty-state">No raw signals loaded yet.</p>}
                  </div>
                </div>
              </>
            ) : (
              <p className="empty-state">Choose an incident to inspect its raw signals and closure state.</p>
            )}
          </div>

          <form className="rca-pane" onSubmit={(event) => { event.preventDefault(); void closeIncident(); }}>
            <div className="section-header">
              <h2>RCA Form</h2>
              <span>Required before closing</span>
            </div>
            <label>
              Incident Start
              <input type="datetime-local" value={rcaForm.start_time} onChange={(event) => setRcaForm({ ...rcaForm, start_time: event.target.value })} />
            </label>
            <label>
              Incident End
              <input type="datetime-local" value={rcaForm.end_time} onChange={(event) => setRcaForm({ ...rcaForm, end_time: event.target.value })} />
            </label>
            <label>
              Root Cause Category
              <select value={rcaForm.root_cause_category} onChange={(event) => setRcaForm({ ...rcaForm, root_cause_category: event.target.value })}>
                {RCA_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label>
              Fix Applied
              <textarea rows={4} value={rcaForm.fix_applied} onChange={(event) => setRcaForm({ ...rcaForm, fix_applied: event.target.value })} />
            </label>
            <label>
              Prevention Steps
              <textarea rows={4} value={rcaForm.prevention_steps} onChange={(event) => setRcaForm({ ...rcaForm, prevention_steps: event.target.value })} />
            </label>
            <button type="submit" disabled={loading || !selectedId}>
              {loading ? 'Closing...' : 'Close incident'}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}
