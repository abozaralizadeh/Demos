import * as SecureStore from 'expo-secure-store';

export type Lang = 'en' | 'it';
export type Value = 'agree' | 'partly' | 'unsure' | 'disagree';

const API = process.env.EXPO_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';
const IDENTITY = process.env.EXPO_PUBLIC_IDENTITY_URL ?? 'http://127.0.0.1:8001';

export type Opening = {
  kind: 'close' | 'needs' | 'news' | 'daily';
  lines: string[];
  topic_id: string | null;
  label?: string;
  quote?: string;
  quote_label?: string;
};

export type Open = {
  people: number;
  sample: boolean;
  consented: boolean;
  unlocked: boolean;
  language: Lang;
  notifications: boolean;
  // Features built but held back by the Proposed answers. The server decides.
  preview: boolean;
  anonymous: boolean;
  display_name: string | null;
  opening: Opening | null;
};

export type Area = 'milan' | 'italy' | 'world';

export type MirrorRow = { stance_id: number | null; claim: string; value: Value | null; word: string };

export type DataBlock = {
  fact_id: number;
  title: string;
  items: { label: string; value: string }[];
  source: string;
  url: string | null;
  placeholder: boolean;
};

export type Reply = {
  conversation_id: string;
  move: string;
  lines: string[];
  theme: 'dark' | 'white';
  mirror: { heard: string; rows: MirrorRow[]; hint: string } | null;
  data: (Partial<DataBlock> & { bar?: number; base?: number }) | null;
  foot: string | null;
  source: string | null;
  bridge: string | null;
  ended: boolean;
  turn_id: number | null;
  unlocked: boolean;
};

export type MapTopic = {
  id: string;
  label: string;
  x: number;
  y: number;
  tilt: number;
  radius: number;
  gap: number | null;
  thin: boolean;
  paused: boolean;
  people: number;
  agreement_id: number | null;
};

export type MapData = { topics: MapTopic[]; links: { topic_a: string; topic_b: string }[] };

export type Card = {
  id: number;
  text: string;
  state: string;
  paused: boolean;
  meters: { label: string; pct: number; base: number }[];
  sent: boolean;
  requests: number;
  requests_needed: number;
  asked?: boolean;
  url?: string;
  petition?: { signatures: number; signed: boolean } | null;
};

export type Fact = {
  id: number;
  topic: string;
  title: string;
  items: { label: string; value: string }[];
  source_name: string;
  year: string;
  url: string | null;
  placeholder: boolean;
  reviewed: boolean;
  review_due: string | null;
};

export type YouData = {
  views: { stance_id: number; value: Value; claim: string }[];
  travel: { heard: number; changed: number; words: string | null };
  moved: { now_value: Value; old_value: Value; claim: string; because: string | null } | null;
  bridges: number;
  agreements: Card[];
};

export class ApiError extends Error {
  constructor(public status: number) {
    super(`HTTP ${status}`);
  }
}

let token: string | null = null;

async function call<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const res = await fetch(API + path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status);
  return res.json() as Promise<T>;
}

export async function loadToken(): Promise<string | null> {
  token = await SecureStore.getItemAsync('session');
  return token;
}

// Stands in for SPID or CIE until a real identity broker is connected.
// The phone keeps one random code, so the same phone is the same person.
// What the dev stub pretends the ID check said, so the error screens can be tried.
export type DevCheck = 'adult' | 'minor' | 'broken';

export async function signInDev(language: Lang, as: DevCheck = 'adult'): Promise<void> {
  let code = await SecureStore.getItemAsync('dev_code');
  if (!code) {
    code = 'DEV' + Math.random().toString(36).slice(2, 14).toUpperCase();
    await SecureStore.setItemAsync('dev_code', code);
  }
  const check = await fetch(IDENTITY + '/verify/dev', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tax_code: code,
      born: as === 'minor' ? `${new Date().getFullYear() - 16}-01-01` : as === 'broken' ? 'unreadable' : '1990-01-01',
    }),
  });
  if (!check.ok) throw new ApiError(check.status);
  const { assertion } = await check.json();
  const session = await call<{ token: string }>('/v1/session', 'POST', { assertion, language });
  token = session.token;
  await SecureStore.setItemAsync('session', session.token);
}

export async function forget(): Promise<void> {
  token = null;
  await SecureStore.deleteItemAsync('session');
  await SecureStore.deleteItemAsync('dev_code');
}

export const api = {
  open: () => call<Open>('/v1/open'),
  consent: () => call<{ ok: boolean }>('/v1/consent', 'POST'),
  withdraw: () => call<{ ok: boolean }>('/v1/consent/withdraw', 'POST'),
  settings: (body: { language?: Lang; notifications?: boolean; anonymous?: boolean; display_name?: string }) =>
    call('/v1/settings', 'PATCH', body),
  start: (opened_by = 'person', topic_id: string | null = null) =>
    call<Reply>('/v1/talk', 'POST', { opened_by, topic_id }),
  say: (id: string, text: string) => call<Reply>(`/v1/talk/${id}/say`, 'POST', { text }),
  fix: (id: string, stance_id: number, value: Value) =>
    call<{ word: string }>(`/v1/talk/${id}/fix`, 'POST', { stance_id, value }),
  report: (turn_id: number) => call<{ message: string }>('/v1/report', 'POST', { turn_id }),
  map: (area: Area = 'milan') => call<MapData>(`/v1/map?area=${area}`),
  fact: (id: number) => call<Fact>(`/v1/facts/${id}`),
  you: () => call<YouData>('/v1/you'),
  agreement: (id: number) => call<Card>(`/v1/agreements/${id}`),
  askToSend: (id: number) => call<{ ok: boolean }>(`/v1/agreements/${id}/send-request`, 'POST'),
  sign: (id: number) => call<{ signed: boolean }>(`/v1/agreements/${id}/sign`, 'POST'),
  exportMe: () => call<Record<string, unknown[]>>('/v1/export'),
  deleteMe: () => call<{ ok: boolean }>('/v1/me', 'DELETE'),
};

export const publicUrl = (id: number, lang: Lang) => `${API}/a/${id}?lang=${lang}`;
