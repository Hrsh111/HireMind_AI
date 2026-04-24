'use client';

import { useCallback, useState } from 'react';
import dynamic from 'next/dynamic';
import { LiveKitRoom } from '@livekit/components-react';
import { InterviewSidebar } from '../components/InterviewSidebar';
import { RoomWorkspace } from '../components/RoomWorkspace';
import { TranscriptPanel } from '../components/TranscriptPanel';
import { ExecuteResponse, RoundType, TranscriptMessage } from '../lib/types';

const Editor = dynamic(() => import('@monaco-editor/react'), { ssr: false });

const DEFAULT_CODE = `# Write your code here\nprint("Ready for Algo")\n`;

function newSessionId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function Page() {
  const [serverUrl, setServerUrl] = useState(process.env.NEXT_PUBLIC_LIVEKIT_URL ?? 'ws://localhost:7880');
  const [roomName, setRoomName] = useState(process.env.NEXT_PUBLIC_DEFAULT_ROOM ?? 'algo-room');
  const [identity, setIdentity] = useState(`candidate-${Math.random().toString(36).slice(2, 8)}`);
  const [sessionId] = useState(() => newSessionId());
  const [token, setToken] = useState(process.env.NEXT_PUBLIC_LIVEKIT_TOKEN ?? '');
  const [tokenLoading, setTokenLoading] = useState(false);
  const [resumeLoading, setResumeLoading] = useState(false);
  const [connect, setConnect] = useState(false);

  // Log connect button presses
  const handleToggleConnect = useCallback(() => {
    setConnect((v) => {
      const newValue = !v;
      console.log(`[Connect Button] Pressed. New connect state:`, newValue);
      return newValue;
    });
  }, []);
  const [roundType, setRoundType] = useState<RoundType>('resume_grill');
  const [resumeText, setResumeText] = useState('');
  const [resumeFileName, setResumeFileName] = useState('');
  const [code, setCode] = useState(DEFAULT_CODE);
  const [running, setRunning] = useState(false);
  const [execution, setExecution] = useState<ExecuteResponse | null>(null);
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);

  const addTranscript = useCallback((msg: TranscriptMessage) => {
    setTranscript((prev) => [...prev.slice(-199), msg]);
  }, []);

  const handleResumeUpload = useCallback(
    async (file: File) => {
      setResumeLoading(true);
      try {
        const form = new FormData();
        form.append('file', file);
        const res = await fetch('/api/parse-resume', { method: 'POST', body: form });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || 'Resume parsing failed');
        setResumeText(String(data.text || ''));
        setResumeFileName(String(data.fileName || file.name));
      } catch (error) {
        addTranscript({
          id: crypto.randomUUID(),
          role: 'system',
          text: `Resume upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
          createdAt: Date.now(),
        });
      } finally {
        setResumeLoading(false);
      }
    },
    [addTranscript]
  );

  const generateToken = useCallback(async () => {
    setTokenLoading(true);
    try {
      const res = await fetch('/api/livekit-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roomName, identity }),
      });
      const data = await res.json();
      if (!res.ok || !data?.token) throw new Error(data?.error || 'Token generation failed');
      setToken(String(data.token));
      addTranscript({ id: crypto.randomUUID(), role: 'system', text: 'LiveKit token generated.', createdAt: Date.now() });
    } catch (error) {
      addTranscript({
        id: crypto.randomUUID(),
        role: 'system',
        text: `Token error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        createdAt: Date.now(),
      });
    } finally {
      setTokenLoading(false);
    }
  }, [addTranscript, identity, roomName]);

  const runCode = useCallback(async () => {
    setRunning(true);
    setExecution(null);
    try {
      const res = await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: 'python', version: '3.10.0', files: [{ name: 'main.py', content: code }] }),
      });
      const data = (await res.json()) as ExecuteResponse;
      setExecution(data);
    } catch (error) {
      setExecution({ error: error instanceof Error ? error.message : 'Execution request failed' });
    } finally {
      setRunning(false);
    }
  }, [code]);

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-6 text-zinc-100">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 lg:grid-cols-3">
        <InterviewSidebar
          serverUrl={serverUrl} setServerUrl={setServerUrl}
          roomName={roomName} setRoomName={setRoomName}
          identity={identity} setIdentity={setIdentity}
          token={token} setToken={setToken}
          roundType={roundType} setRoundType={setRoundType}
          resumeText={resumeText} setResumeText={setResumeText}
          resumeFileName={resumeFileName}
          onResumeUpload={handleResumeUpload} resumeLoading={resumeLoading}
          connect={connect} onToggleConnect={handleToggleConnect}
          onGenerateToken={generateToken} tokenLoading={tokenLoading}
        />

        <section className="border border-zinc-800 bg-zinc-950 p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-semibold text-zinc-50">Code editor</h2>
            <button onClick={runCode} disabled={running}
              className="bg-lime-500 px-3 py-2 text-sm font-semibold text-zinc-950 hover:bg-lime-400 disabled:opacity-60">
              {running ? 'Running...' : 'Run'}
            </button>
          </div>

          <div className="h-[440px] overflow-hidden border border-zinc-800">
            <Editor height="100%" defaultLanguage="python" value={code} theme="vs-dark"
              onChange={(v) => setCode(v ?? '')}
              options={{ minimap: { enabled: false }, fontSize: 14, wordWrap: 'on' }} />
          </div>

          <div className="mt-3 border border-zinc-800 bg-zinc-900 p-3 text-sm">
            <p className="mb-2 text-xs text-zinc-400">Execution output</p>
            <pre className="max-h-52 overflow-auto whitespace-pre-wrap text-zinc-100">
              {execution?.run?.stdout || execution?.run?.output || execution?.stdout || execution?.output || execution?.run?.stderr || execution?.stderr || execution?.error || 'No output yet.'}
            </pre>
            <p className="mt-2 text-xs text-zinc-500">Source: {execution?.source ?? 'none'}</p>
          </div>

          <LiveKitRoom serverUrl={serverUrl} token={token || undefined}
            connect={connect && Boolean(token)} audio={true} video={false}
            onConnected={() => addTranscript({ id: crypto.randomUUID(), role: 'system', text: 'Connected to LiveKit room.', createdAt: Date.now() })}
            onDisconnected={() => addTranscript({ id: crypto.randomUUID(), role: 'system', text: 'Disconnected from LiveKit room.', createdAt: Date.now() })}
            onError={(err) => addTranscript({ id: crypto.randomUUID(), role: 'system', text: `LiveKit error: ${err.message}`, createdAt: Date.now() })}
            className="mt-3">
            <RoomWorkspace sessionId={sessionId} roundType={roundType}
              resumeText={resumeText} resumeFileName={resumeFileName}
              code={code} connected={connect && Boolean(token)} onTranscript={addTranscript} />
          </LiveKitRoom>
        </section>

        <div className="lg:col-span-3">
          <TranscriptPanel items={transcript} />
        </div>
      </div>
    </main>
  );
}
