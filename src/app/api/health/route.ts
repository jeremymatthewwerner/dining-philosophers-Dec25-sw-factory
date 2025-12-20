import { NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function GET() {
  let dbStatus = 'disconnected';
  try {
    await prisma.$queryRaw`SELECT 1`;
    dbStatus = 'connected';
  } catch {}
  
  return NextResponse.json({
    status: dbStatus === 'connected' ? 'ok' : 'degraded',
    timestamp: new Date().toISOString(),
    database: dbStatus,
    websocket: 'active'
  });
}
