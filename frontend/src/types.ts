export type IncidentStatus = 'OPEN' | 'INVESTIGATING' | 'RESOLVED' | 'CLOSED';

export type Incident = {
  id: string;
  component_id: string;
  component_type: string;
  severity: 'P0' | 'P1' | 'P2' | 'P3';
  alert_type: string;
  status: IncidentStatus;
  first_signal_at: string;
  last_signal_at: string;
  signal_count: number;
  mttr_minutes: number | null;
  rca: {
    start_time: string;
    end_time: string;
    root_cause_category: string;
    fix_applied: string;
    prevention_steps: string;
  } | null;
  signals?: Array<Record<string, unknown>>;
};

export type IncidentSummary = Incident;
