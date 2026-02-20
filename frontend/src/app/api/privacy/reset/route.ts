import { NextRequest, NextResponse } from 'next/server';

const GATEWAY = process.env.API_GATEWAY_URL || 'http://localhost:3001';

export async function POST(req: NextRequest) {
  const body = await req.text();
  const cookie = req.headers.get('cookie') ?? '';

  const upstream = await fetch(`${GATEWAY}/api/privacy/reset`, {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      cookie,
    },
    body,
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
