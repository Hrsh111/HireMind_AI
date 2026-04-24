'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  RoomAudioRenderer,
  StartAudio,
  useLocalParticipant,
  useRoomContext,
} from '@livekit/components-react';
import { DataPacket_Kind, RoomEvent } from 'livekit-client';
import { RoundType, TranscriptMessage } from '../lib/types';

type Props = {
  sessionId: string;
  roundType: RoundType;
  resumeText: string;
  resumeFileName: string;
  code: string;
  connected: boolean;
  onTranscript: (msg: TranscriptMessage) => void;
};

export function RoomWorkspace({
  sessionId,
  roundType,
  resumeText,
  resumeFileName,
  code,
  connected,
  onTranscript,
}: Props) {
  const room = useRoomContext();
  const { localParticipant } = useLocalParticipant();
  const [screenSharing, setScreenSharing] = useState(false);
  const [manualInput, setManualInput] = useState('');
  const sentContextRef = useRef(false);

  const publishData = useCallback(
    async (payload: Record<string, unknown>, topic: string) => {
      if (!localParticipant) return;
      const encoded = new TextEncoder().encode(JSON.stringify(payload));

      try {
        await localParticipant.publishData(encoded, { reliable: true, topic });
      } catch {
        await localParticipant.publishData(encoded, { reliable: true });
      }
    },
    [localParticipant]
  );

  useEffect(() => {
    if (!room) return;

    const onData = (
      payload: Uint8Array,
      participant?: { identity?: string },
      _kind?: DataPacket_Kind,
      _topic?: string
    ) => {
      try {
        const data = JSON.parse(new TextDecoder().decode(payload));

        if (data?.type === 'agent_handoff') {
          onTranscript({
            id: crypto.randomUUID(),
            role: 'agent',
            text: String(data.text ?? ''),
            agentName: String(data.agent_name ?? 'Agent'),
            avatar: String(data.avatar ?? 'Q'),
            reason: String(data.reason ?? ''),
            createdAt: Date.now(),
          });
          return;
        }

        if (data?.type === 'agent_message' || data?.text) {
          onTranscript({
            id: crypto.randomUUID(),
            role: data.role === 'user' ? 'user' : 'agent',
            text: String(data.text ?? ''),
            agentName:
              data.role === 'user'
                ? participant?.identity ?? 'You'
                : String(data.agent_name ?? 'Algo'),
            avatar: String(data.avatar ?? (data.role === 'user' ? 'U' : 'Q')),
            createdAt: Date.now(),
          });
        }
      } catch {
        // ignore non-JSON payloads
      }
    };

    room.on(RoomEvent.DataReceived, onData);
    return () => {
      room.off(RoomEvent.DataReceived, onData);
    };
  }, [room, onTranscript]);

  useEffect(() => {
    if (!connected) {
      sentContextRef.current = false;
      return;
    }
    if (sentContextRef.current || !localParticipant) return;

    sentContextRef.current = true;
    publishData(
      {
        type: 'interview_context',
        session_id: sessionId,
        round_type: roundType,
        resume_text: resumeText,
        resume_file_name: resumeFileName,
        sent_at: new Date().toISOString(),
      },
      'interview-context'
    ).catch((err) => {
      onTranscript({
        id: crypto.randomUUID(),
        role: 'system',
        text: `Failed to publish JD/Resume context: ${err instanceof Error ? err.message : 'Unknown error'}`,
        createdAt: Date.now(),
      });
    });
  }, [connected, sessionId, roundType, resumeText, resumeFileName, localParticipant, onTranscript, publishData]);

  useEffect(() => {
    if (!connected || !localParticipant) return;

    const timer = setTimeout(() => {
      publishData(
        {
          type: 'code_update',
          session_id: sessionId,
          code,
          sent_at: new Date().toISOString(),
        },
        'code-update'
      ).catch((err) => {
        onTranscript({
          id: crypto.randomUUID(),
          role: 'system',
          text: `Failed to publish code update: ${err instanceof Error ? err.message : 'Unknown error'}`,
          createdAt: Date.now(),
        });
      });
    }, 300);

    return () => clearTimeout(timer);
  }, [code, connected, sessionId, localParticipant, onTranscript, publishData]);

  const toggleScreenShare = useCallback(async () => {
    try {
      const next = !screenSharing;
      await localParticipant?.setScreenShareEnabled(next);
      setScreenSharing(next);
      onTranscript({
        id: crypto.randomUUID(),
        role: 'system',
        text: next
          ? 'Screen sharing enabled. Agent receives your screen stream.'
          : 'Screen sharing disabled.',
        createdAt: Date.now(),
      });
    } catch (error) {
      onTranscript({
        id: crypto.randomUUID(),
        role: 'system',
        text: `Screen share failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        createdAt: Date.now(),
      });
    }
  }, [localParticipant, onTranscript, screenSharing]);

  const sendManualTurn = useCallback(async () => {
    const text = manualInput.trim();
    if (!text) return;

    setManualInput('');
    onTranscript({
      id: crypto.randomUUID(),
      role: 'user',
      text,
      agentName: 'You',
      avatar: 'U',
      createdAt: Date.now(),
    });

    try {
      await publishData(
        {
          type: 'user_utterance',
          session_id: sessionId,
          round_type: roundType,
          text,
          sent_at: new Date().toISOString(),
        },
        'user-utterance'
      );
    } catch (err) {
      onTranscript({
        id: crypto.randomUUID(),
        role: 'system',
        text: `Failed to send manual turn: ${err instanceof Error ? err.message : 'Unknown error'}`,
        createdAt: Date.now(),
      });
    }
  }, [manualInput, sessionId, roundType, onTranscript, publishData]);

  return (
    <div className="mt-3 border border-zinc-800 bg-zinc-950 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={toggleScreenShare}
          className="bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
        >
          {screenSharing ? 'Stop Screen Share' : 'Share Screen'}
        </button>

        <StartAudio
          label="Enable Audio"
          className="bg-cyan-600 px-3 py-2 text-sm font-medium text-zinc-950 hover:bg-cyan-400"
        />
      </div>

      <div className="mt-3 flex gap-2">
        <input
          value={manualInput}
          onChange={(e) => setManualInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              void sendManualTurn();
            }
          }}
          placeholder="Type an answer or request a follow-up"
          className="w-full border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
        />
        <button
          onClick={() => void sendManualTurn()}
          className="bg-cyan-600 px-3 py-2 text-sm font-medium text-zinc-950 hover:bg-cyan-400"
        >
          Send
        </button>
      </div>

      <RoomAudioRenderer />
    </div>
  );
}
