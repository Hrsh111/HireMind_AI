'use client';

import { TranscriptMessage } from '../lib/types';

function formatTranscript(items: TranscriptMessage[]): string {
  return items
    .map((msg) => {
      const time = new Date(msg.createdAt).toLocaleTimeString();
      const speaker = msg.agentName ?? (msg.role === 'user' ? 'You' : 'System');
      const reason = msg.reason ? `\n  Reason: ${msg.reason}` : '';
      return `[${time}] ${speaker} (${msg.role}): ${msg.text}${reason}`;
    })
    .join('\n');
}

export function TranscriptPanel({ items }: { items: TranscriptMessage[] }) {
  const downloadTranscript = () => {
    const content = formatTranscript(items);
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `transcript-${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  return (
    <section className="border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-50">Transcript</h2>
        <button
          onClick={downloadTranscript}
          disabled={items.length === 0}
          className="bg-cyan-600 px-3 py-2 text-sm font-medium text-zinc-950 hover:bg-cyan-400 disabled:opacity-60"
        >
          Download transcript
        </button>
      </div>
      <div className="max-h-[340px] overflow-auto pr-1">
        {items.length === 0 ? <p className="text-sm text-zinc-400">No messages yet.</p> : null}
        {items.map((msg) => (
          <div key={msg.id} className="mb-2 border border-zinc-800 bg-zinc-900 p-2">
            <div className="mb-1 flex items-center gap-2 text-xs text-zinc-300">
              <span className="inline-flex h-6 w-6 items-center justify-center border border-zinc-700 bg-zinc-950 text-[10px]">
                {msg.avatar ?? (msg.role === 'user' ? 'U' : msg.role === 'agent' ? 'Q' : 'I')}
              </span>
              <span className="font-semibold">{msg.agentName ?? (msg.role === 'user' ? 'You' : 'System')}</span>
              <span className="text-zinc-500">{new Date(msg.createdAt).toLocaleTimeString()}</span>
            </div>
            <p className="text-sm text-zinc-100">{msg.text}</p>
            {msg.reason ? <p className="mt-1 text-xs text-zinc-400">Reason: {msg.reason}</p> : null}
          </div>
        ))}
      </div>
    </section>
  );
}
