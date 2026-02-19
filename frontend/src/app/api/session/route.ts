import { NextRequest, NextResponse } from 'next/server';

const GATEWAY_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export async function DELETE(request: NextRequest) {
  try {
    const res = await fetch(`${GATEWAY_URL}/api/session`, {
      method: 'DELETE',
      headers: {
        ...(request.headers.get('cookie')
          ? { Cookie: request.headers.get('cookie')! }
          : {}),
      },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: 'Failed to clear session' }, { status: 503 });
  }
}
