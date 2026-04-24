'use client';

import { useCallback, useState } from 'react';
import Editor from '@monaco-editor/react';
import { LiveKitRoom } from '@livekit/components-react';
import { InterviewSidebar } from '../components/InterviewSidebar';
import { RoomWorkspace } from '../components/RoomWorkspace';
import { TranscriptPanel } from '../components/TranscriptPanel';
import { ExecuteResponse, TranscriptMessage } from '../lib/types';

const DEFAULT_CODE = `# Write your code here\nprint("Hello, Algo!")\n`;

export default function Page() {
  const [serverUrl, setServerUrl] = useState(process.env.NEXT_PUBLIC_LIVEKIT_URL ?? 'ws://localhost:7880');
  const [roomName, setRoomName] = useState(process.env.NEXT_PUBLIC_DEFAULT_ROOM ?? 'algo-room');
  const [identity, setIdentity] = useState(`candidate-${Math.random().toString(36).slice(2, 8)}`);
  const [token, setToken] = useState(process.env.NEXT_PUBLIC_LIVEKIT_TOKEN ?? '');
  const [tokenLoading, setTokenLoading] = useState(false);
  const [connect, setConnect] = useState(false);
  const [jdText, setJdText] = useState('');
  const [resumeText, setResumeText] = useState('');
  const [code, setCode] = useState(DEFAULT_CODE);
  const [running, setRunning] = useState(false);
  const [execution, setExecution] = useState<ExecuteResponse | null>(null);
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);

  const addTranscript = useCallback((msg: TranscriptMessage) => {
    setTranscript((prev) => [...prev.slice(-199), msg]);
  }, []);

  const generateToken = useCallback(async () => {
    setTokenLoading(true);
    try {
      const res = await fetch('/api/livekit-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roomName, identity }),
      });
      const data = await res.json();
      if (!res.ok || !data?.token) {
        throw new Error(data?.error || 'Token generation failed');
      }
      setToken(String(data.token));
      addTranscript({
        id: crypto.randomUUID(),
        role: 'system',
        text: 'LiveKit token generated.',
        createdAt: Date.now(),
      });
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
        body: JSON.stringify({
          language: 'python',
          version: '3.10.0',
          files: [{ name: 'main.py', content: code }],
        }),
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
    <main className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 lg:grid-cols-3">
        <InterviewSidebar
          serverUrl={serverUrl}
          setServerUrl={setServerUrl}
          roomName={roomName}
          setRoomName={setRoomName}
          identity={identity}
          setIdentity={setIdentity}
          token={token}
          setToken={setToken}
          jdText={jdText}
          setJdText={setJdText}
          resumeText={resumeText}
          setResumeText={setResumeText}
          connect={connect}
          onToggleConnect={() => setConnect((v) => !v)}
          onGenerateToken={generateToken}
          tokenLoading={tokenLoading}
        />

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-semibold">Code Editor</h2>
            <button
              onClick={runCode}
              disabled={running}
              className="rounded-md bg-amber-500 px-3 py-2 text-sm font-semibold text-black hover:bg-amber-400 disabled:opacity-60"
            >
              {running ? 'Running...' : 'Run'}
            </button>
          </div>

          <div className="h-[440px] overflow-hidden rounded-md border border-slate-800">
            <Editor
              height="100%"
              defaultLanguage="python"
              value={code}
              theme="vs-dark"
              onChange={(v) => setCode(v ?? '')}
              options={{ minimap: { enabled: false }, fontSize: 14 }}
            />
          </div>

          <div className="mt-3 rounded-md border border-slate-800 bg-slate-950 p-3 text-sm">
            <p className="mb-2 text-xs text-slate-400">Execution Output</p>
            <pre className="max-h-52 overflow-auto whitespace-pre-wrap text-slate-200">
{execution?.run?.stdout || execution?.run?.output || execution?.stdout || execution?.output || execution?.run?.stderr || execution?.stderr || execution?.error || 'No output yet.'}
            </pre>
            <p className="mt-2 text-xs text-slate-500">
              Source: {execution?.source ?? 'none'}
            </p>
          </div>

          <LiveKitRoom
            serverUrl={serverUrl}
            token={token || undefined}
            connect={connect && Boolean(token)}
            audio={true}
            video={false}
            onConnected={() => {
              addTranscript({
                id: crypto.randomUUID(),
                role: 'system',
                text: 'Connected to LiveKit room.',
                createdAt: Date.now(),
              });
            }}
            onDisconnected={() => {
              addTranscript({
                id: crypto.randomUUID(),
                role: 'system',
                text: 'Disconnected from LiveKit room.',
                createdAt: Date.now(),
              });
            }}
            onError={(err) => {
              addTranscript({
                id: crypto.randomUUID(),
                role: 'system',
                text: `LiveKit error: ${err.message}`,
                createdAt: Date.now(),
              });
            }}
            className="mt-3"
          >
            <RoomWorkspace
              jdText={jdText}
              resumeText={resumeText}
              code={code}
              connected={connect && Boolean(token)}
              onTranscript={addTranscript}
            />
          </LiveKitRoom>
        </section>

        <div className="lg:col-span-3">
          <TranscriptPanel items={transcript} />
        </div>
      </div>
    </main>
  );
}
