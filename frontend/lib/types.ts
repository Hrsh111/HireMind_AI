export type TranscriptMessage = {
  id: string;
  role: 'agent' | 'user' | 'system';
  text: string;
  agentName?: string;
  avatar?: string;
  reason?: string;
  createdAt: number;
};

export type RoundType = 'resume_grill' | 'dsa' | 'systems' | 'behavioral';

export type InterviewContextPayload = {
  type: 'interview_context';
  session_id: string;
  round_type: RoundType;
  resume_text: string;
  resume_file_name?: string;
  sent_at: string;
};

export type ExecuteRequest = {
  language: string;
  version: string;
  files: Array<{ name: string; content: string }>;
  stdin?: string;
};

export type ExecuteResponse = {
  run?: {
    stdout?: string;
    stderr?: string;
    output?: string;
    code?: number;
    signal?: string;
  };
  stdout?: string;
  stderr?: string;
  output?: string;
  code?: number;
  error?: string;
  source?: 'piston' | 'local-fallback';
};
