import { NextRequest, NextResponse } from 'next/server';
import { execFile } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { ExecuteRequest, ExecuteResponse } from '../../../lib/types';

const execFileAsync = promisify(execFile);
const PISTON_URL = 'https://emkc.org/api/v2/piston/execute';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function normalizeBody(body: Partial<ExecuteRequest>): ExecuteRequest {
  return {
    language: body.language || 'python',
    version: body.version || '3.10.0',
    files:
      body.files && body.files.length > 0
        ? body.files
        : [{ name: 'main.py', content: 'print("Hello")' }],
    stdin: body.stdin || '',
  };
}

async function executeWithPiston(payload: ExecuteRequest): Promise<ExecuteResponse> {
  const controller = new AbortController();
  const timeoutMs = Number(process.env.PISTON_TIMEOUT_MS || '12000');
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(PISTON_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const data = (await response.json().catch(() => ({}))) as ExecuteResponse;
    if (!response.ok) {
      return {
        source: 'piston',
        error: `Piston request failed with status ${response.status}.`,
        ...data,
      };
    }

    return { source: 'piston', ...data };
  } finally {
    clearTimeout(timer);
  }
}

async function executeWithLocalFallback(payload: ExecuteRequest): Promise<ExecuteResponse> {
  const allowFallback = (process.env.EXECUTE_FALLBACK || '').toLowerCase() === 'local';
  if (!allowFallback) {
    return {
      source: 'local-fallback',
      error: 'Local fallback disabled. Set EXECUTE_FALLBACK=local to enable demo fallback.',
    };
  }

  if (payload.language.toLowerCase() !== 'python') {
    return {
      source: 'local-fallback',
      error: 'Local fallback currently supports Python only.',
    };
  }

  const timeoutMs = Number(process.env.LOCAL_EXEC_TIMEOUT_MS || '4000');
  const memoryKb = Number(process.env.LOCAL_EXEC_MEMORY_KB || '262144');
  const maxBuffer = Number(process.env.LOCAL_EXEC_MAX_BUFFER || '65536');

  const workdir = await mkdtemp(join(tmpdir(), 'algo-exec-'));

  try {
    const code = payload.files[0]?.content ?? '';
    const filename = payload.files[0]?.name || 'main.py';
    const safeName = filename.replace(/[^a-zA-Z0-9_.-]/g, '_');
    const targetFile = join(workdir, safeName);
    await writeFile(targetFile, code, 'utf-8');

    const command = `ulimit -v ${memoryKb}; python3 ${safeName}`;
    const { stdout, stderr } = await execFileAsync('bash', ['-lc', command], {
      cwd: workdir,
      timeout: timeoutMs,
      maxBuffer,
    });

    return {
      source: 'local-fallback',
      run: {
        stdout,
        stderr,
        output: `${stdout || ''}${stderr || ''}`,
        code: 0,
      },
    };
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Local execution failed.';
    return {
      source: 'local-fallback',
      run: {
        stderr: msg,
        output: msg,
        code: 1,
      },
      error: msg,
    };
  } finally {
    await rm(workdir, { recursive: true, force: true });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json().catch(() => ({}))) as Partial<ExecuteRequest>;
    const payload = normalizeBody(body);

    const pistonResult = await executeWithPiston(payload);
    const run = pistonResult.run;
    const hasRunOutput = Boolean(run?.stdout || run?.stderr || run?.output || run?.code === 0);

    // If Piston has a usable run result, return it directly.
    if (hasRunOutput && !pistonResult.error) {
      return NextResponse.json(pistonResult);
    }

    // Slow/failure path: local demo fallback.
    const fallback = await executeWithLocalFallback(payload);
    if (!fallback.error) {
      return NextResponse.json(fallback);
    }

    return NextResponse.json(
      {
        source: 'piston',
        error: pistonResult.error || fallback.error || 'Execution failed.',
        piston: pistonResult,
        fallback,
      },
      { status: 502 }
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unexpected execute error.' },
      { status: 500 }
    );
  }
}
