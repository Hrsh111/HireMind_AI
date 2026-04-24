import { TranscriptMessage } from '../lib/types';

export function TranscriptPanel({ items }: { items: TranscriptMessage[] }) {
  return (
    <section className="border border-zinc-800 bg-zinc-950 p-4">
      <h2 className="mb-3 text-base font-semibold text-zinc-50">Transcript</h2>
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
