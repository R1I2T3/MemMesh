export interface Team {
  team_id: string;
  name: string;
}

export interface User {
  user_id: string;
  email: string;
  role: string;
}

export interface TeamMember {
  team_id: string;
  user_id: string;
  role: string;
}

export interface DocumentItem {
  parent_id: string;
  filename: string;
  created_at: string | null;
  version_number: number;
}

export interface UploadTask {
  id: string;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
  taskId: string;
}

export interface Message {
  message_id: string;
  session_id: string;
  parent_message_id: string | null;
  role: 'user' | 'assistant';
  content: string;
  created_at: string | null;
  citations?: any[];
}

export interface Citation {
  type?: 'pdf' | 'web' | string;
  content: string;
  source?: string;
  url?: string;
  page_number?: number;
  bbox?: number[];
  parent_id?: string;
}

export interface EvalScorePoint {
  date: string;
  faithfulness: number;
  hallucination: number;
  relevancy: number;
}

export interface AnalyticsData {
  queries_last_hour: number;
  queries_last_day: number;
  avg_latency_ms: number;
  unique_users_last_day: number;
  positive_feedback: number;
  total_feedback: number;
  message?: string;
}
