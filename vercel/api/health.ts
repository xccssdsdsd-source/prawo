import type { VercelRequest, VercelResponse } from '@vercel/node';
import { query } from '../lib/db';
import { VERSION, sendJson, setCors } from '../lib/http';
import { SQL_HEALTH } from '../lib/law';
import { dataInfo, dataAsOf } from '../lib/datainfo';

export default async function handler(req: VercelRequest, res: VercelResponse): Promise<void> {
  setCors(res);
  if (req.method === 'OPTIONS') {
    res.status(204).end();
    return;
  }
  try {
    const [r] = await query<{ documents: number; chunks: number }>(SQL_HEALTH);
    sendJson(res, { ok: true, db: true, documents: r.documents, chunks: r.chunks, version: VERSION, data_as_of: dataAsOf, data_info: dataInfo });
  } catch {
    sendJson(res, { ok: false, db: false, documents: 0, chunks: 0, version: VERSION, data_as_of: dataAsOf, data_info: dataInfo }, 503);
  }
}
