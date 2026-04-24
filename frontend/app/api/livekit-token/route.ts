import { NextRequest, NextResponse } from 'next/server';
import { AccessToken } from 'livekit-server-sdk';

export const runtime = 'nodejs';

export async function POST(req: NextRequest) {
  try {
    const apiKey = process.env.LIVEKIT_API_KEY;
    const apiSecret = process.env.LIVEKIT_API_SECRET;

    if (!apiKey || !apiSecret) {
      return NextResponse.json(
        { error: 'Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET environment variable.' },
        { status: 500 }
      );
    }

    const body = await req.json().catch(() => ({}));
    const roomName = String(body?.roomName || process.env.NEXT_PUBLIC_DEFAULT_ROOM || 'algo-room');
    const identity = String(body?.identity || `candidate-${Math.random().toString(36).slice(2, 8)}`);

    const token = new AccessToken(apiKey, apiSecret, {
      identity,
      name: identity,
      ttl: '30m',
    });

    token.addGrant({
      roomJoin: true,
      room: roomName,
      canPublish: true,
      canSubscribe: true,
      canPublishData: true,
    });

    const jwt = await token.toJwt();
    return NextResponse.json({ token: jwt, identity, roomName });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to generate token.' },
      { status: 500 }
    );
  }
}
