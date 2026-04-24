import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const MAX_UPLOAD_BYTES = 8 * 1024 * 1024;

export async function POST(req: NextRequest) {
  try {
    const form = await req.formData();
    const file = form.get('file');

    if (!(file instanceof File)) {
      return NextResponse.json({ error: 'Missing resume file.' }, { status: 400 });
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      return NextResponse.json({ error: 'Resume file must be 8 MB or smaller.' }, { status: 413 });
    }

    const buffer = Buffer.from(await file.arrayBuffer());
    const name = file.name || 'resume';
    const lowerName = name.toLowerCase();
    const contentType = file.type.toLowerCase();

    if (contentType.includes('pdf') || lowerName.endsWith('.pdf')) {
      const pdfParse = (await import('pdf-parse')).default;
      const parsed = await pdfParse(buffer);
      return NextResponse.json({
        fileName: name,
        text: parsed.text?.trim() || '',
      });
    }

    if (
      contentType.startsWith('text/') ||
      lowerName.endsWith('.txt') ||
      lowerName.endsWith('.md') ||
      lowerName.endsWith('.csv')
    ) {
      return NextResponse.json({
        fileName: name,
        text: buffer.toString('utf-8').trim(),
      });
    }

    return NextResponse.json(
      { error: 'Unsupported resume type. Upload PDF, TXT, MD, or CSV.' },
      { status: 415 }
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Could not parse resume.' },
      { status: 500 }
    );
  }
}
