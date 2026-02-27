/**
 * Next.js App Router API route — POST /api/chat
 *
 * Acts as a same-origin proxy to avoid CORS complexity in the browser.
 * The frontend calls this Next.js route; this route forwards the request
 * to the Express API gateway (on port 3001) and returns the response.
 *
 * This pattern keeps credentials (session cookies) same-origin and
 * simplifies CSP/CORS headers on the frontend.
 */

import { NextRequest, NextResponse } from 'next/server';

const GATEWAY_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Forward the request to the Express gateway
    const gatewayRes = await fetch(`${GATEWAY_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Forward session cookie if present
        ...(request.headers.get('cookie')
          ? { Cookie: request.headers.get('cookie')! }
          : {}),
      },
      body: JSON.stringify(body),
    });

    const data = await gatewayRes.json();

    if (!gatewayRes.ok) {
      return NextResponse.json(data, { status: gatewayRes.status });
    }

    // Forward Set-Cookie headers from the gateway to the browser
    const response = NextResponse.json(data, { status: 200 });
    const setCookie = gatewayRes.headers.get('set-cookie');
    if (setCookie) {
      response.headers.set('set-cookie', setCookie);
    }

    return response;
  } catch (error: unknown) {
    console.error('[next-api-chat]', error);
    return NextResponse.json(
      { error: 'Failed to connect to AI service' },
      { status: 503 }
    );
  }
}
