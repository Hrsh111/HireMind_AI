import { Dispatch, SetStateAction } from 'react';

type Props = {
  serverUrl: string;
  setServerUrl: Dispatch<SetStateAction<string>>;
  roomName: string;
  setRoomName: Dispatch<SetStateAction<string>>;
  identity: string;
  setIdentity: Dispatch<SetStateAction<string>>;
  token: string;
  setToken: Dispatch<SetStateAction<string>>;
  jdText: string;
  setJdText: Dispatch<SetStateAction<string>>;
  resumeText: string;
  setResumeText: Dispatch<SetStateAction<string>>;
  connect: boolean;
  onToggleConnect: () => void;
  onGenerateToken: () => Promise<void>;
  tokenLoading: boolean;
};

export function InterviewSidebar(props: Props) {
  return (
    <section className="space-y-3 rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h1 className="text-lg font-semibold">Algo Multi-Agent Interview</h1>

      <label className="block text-xs text-slate-300">LiveKit URL</label>
      <input
        value={props.serverUrl}
        onChange={(e) => props.setServerUrl(e.target.value)}
        className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
      />

      <label className="block text-xs text-slate-300">Room Name</label>
      <input
        value={props.roomName}
        onChange={(e) => props.setRoomName(e.target.value)}
        className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
      />

      <label className="block text-xs text-slate-300">Identity</label>
      <input
        value={props.identity}
        onChange={(e) => props.setIdentity(e.target.value)}
        className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
      />

      <label className="block text-xs text-slate-300">LiveKit Token</label>
      <textarea
        value={props.token}
        onChange={(e) => props.setToken(e.target.value)}
        rows={3}
        className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs"
      />

      <button
        onClick={props.onGenerateToken}
        disabled={props.tokenLoading}
        className="w-full rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
      >
        {props.tokenLoading ? 'Generating Token...' : 'Generate Token'}
      </button>

      <label className="block text-xs text-slate-300">Job Description</label>
      <textarea
        value={props.jdText}
        onChange={(e) => props.setJdText(e.target.value)}
        rows={5}
        className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
      />

      <label className="block text-xs text-slate-300">Resume</label>
      <textarea
        value={props.resumeText}
        onChange={(e) => props.setResumeText(e.target.value)}
        rows={5}
        className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
      />

      <button
        onClick={props.onToggleConnect}
        className={`w-full rounded-md px-3 py-2 text-sm font-semibold ${
          props.connect ? 'bg-rose-600 hover:bg-rose-500' : 'bg-blue-600 hover:bg-blue-500'
        }`}
      >
        {props.connect ? 'Disconnect' : 'Connect'}
      </button>
    </section>
  );
}
