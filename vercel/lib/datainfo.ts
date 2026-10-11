import info from '../public/data-info.json';

/** Zawartość public/data-info.json (generowana skryptem) lub null. */
export const dataInfo: Record<string, unknown> | null =
  info && typeof info === 'object' ? (info as Record<string, unknown>) : null;

/** Data stanu danych YYYY-MM-DD lub null. */
export const dataAsOf: string | null =
  typeof dataInfo?.data_as_of === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dataInfo.data_as_of as string)
    ? (dataInfo.data_as_of as string)
    : null;
