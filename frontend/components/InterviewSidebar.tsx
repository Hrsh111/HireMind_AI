import { Dispatch, SetStateAction } from 'react';
import { RoundType } from '../lib/types';

const ROUND_OPTIONS: Array<{ value: RoundType; label: string }> = [
  { value: 'resume_grill', label: 'Resume grill' },
  { value: 'dsa', label: 'DSA' },
  { value: 'systems', label: 'Systems' },
  { value: 'behavioral', label: 'Behavioral' },
];

type Props = {
  serverUrl: string;
  setServerUrl: Dispatch<SetStateAction<string>>;
  roomName: string;
  setRoomName: Dispatch<SetStateAction<string>>;
  identity: string;
  setIdentity: Dispatch<SetStateAction<string>>;
  token: string;
  setToken: Dispatch<SetStateAction<string>>;
  roundType: RoundType;
  setRoundType: Dispatch<SetStateAction<RoundType>>;
  resumeText: string;
  setResumeText: Dispatch<SetStateAction<string>>;
  resumeFileName: string;
  onResumeUpload: (file: File) => Promise<void>;
  resumeLoading: boolean;
  connect: boolean;
  onToggleConnect: () => void;
  onGenerateToken: () => Promise<void>;
  tokenLoading: boolean;
};

export function InterviewSidebar(props: Props) {
  return (
    <section className="space-y-3 border border-zinc-800 bg-zinc-950 p-4">
      <h1 className="text-lg font-semibold text-zinc-50">Algo Interview Room</h1>

      <div className="grid grid-cols-2 gap-2">
        {ROUND_OPTIONS.map((round) => (
          <button
            key={round.value}
            onClick={() => props.setRoundType(round.value)}
            className={`border px-3 py-2 text-sm ${
              props.roundType === round.value
                ? 'border-cyan-400 bg-cyan-950 text-cyan-100'
                : 'border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800'
            }`}
          >
            {round.label}
          </button>
        ))}
      </div>

      <label className="block text-xs text-zinc-300">Resume upload</label>
      <input
        type="file"
        accept=".pdf,.txt,.md,.csv,text/plain,application/pdf"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void props.onResumeUpload(file);
        }}
        className="w-full border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200"
      />
      <p className="min-h-5 text-xs text-zinc-500">
        {props.resumeLoading ? 'Parsing resume...' : props.resumeFileName || 'PDF or text file'}
      </p>

      <label className="block text-xs text-zinc-300">Resume text</label>
      <textarea
        value={props.resumeText}
        onChange={(e) => props.setResumeText(e.target.value)}
        rows={8}
        className="w-full border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
      />

      <label className="block text-xs text-zinc-300">LiveKit URL</label>
      <input
        value={props.serverUrl}
        onChange={(e) => props.setServerUrl(e.target.value)}
        className="w-full border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
      />

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs text-zinc-300">Room</label>
          <input
            value={props.roomName}
            onChange={(e) => props.setRoomName(e.target.value)}
            className="w-full border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
          />
        </div>
        <div>
          <label className="block text-xs text-zinc-300">Identity</label>
          <input
            value={props.identity}
            onChange={(e) => props.setIdentity(e.target.value)}
            className="w-full border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
          />
        </div>
      </div>

      <label className="block text-xs text-zinc-300">Token</label>
      <textarea
        value={props.token}
        onChange={(e) => props.setToken(e.target.value)}
        rows={3}
        className="w-full border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-100"
      />

      <button
        onClick={props.onGenerateToken}
        disabled={props.tokenLoading}
        className="w-full bg-cyan-600 px-3 py-2 text-sm font-semibold text-zinc-950 hover:bg-cyan-400 disabled:opacity-60"
      >
        {props.tokenLoading ? 'Generating...' : 'Generate token'}
      </button>

      <button
        onClick={props.onToggleConnect}
        className={`w-full px-3 py-2 text-sm font-semibold ${
          props.connect ? 'bg-red-700 text-white hover:bg-red-600' : 'bg-lime-500 text-zinc-950 hover:bg-lime-400'
        }`}
      >
        {props.connect ? 'Disconnect' : 'Connect'}
      </button>
    </section>
  );
}
