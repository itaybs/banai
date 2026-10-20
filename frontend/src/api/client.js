import { API_BASE_URL } from '../config.js';

/** A failed API call. `status` is the HTTP status (0 for network errors); `code` is the server's error code. */
export class ApiError extends Error {
  constructor(message, { status = 0, code = 'NETWORK_ERROR' } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

async function request(path, fetchImpl, init) {
  if (!API_BASE_URL) throw new Error('The API base URL is not configured');
  let response;
  try {
    response = await (init ? fetchImpl(`${API_BASE_URL}${path}`, init) : fetchImpl(`${API_BASE_URL}${path}`));
  } catch {
    throw new ApiError('Could not reach the design service.');
  }
  let body = null;
  try {
    body = await response.json();
  } catch {
    // non-JSON error pages fall through to the status check below
  }
  if (!response.ok || !body || body.success !== true) {
    const error = body?.success === false && typeof body.error === 'object' ? body.error : null;
    const fallback = response.ok
      ? `Request to ${path} returned an unsuccessful response`
      : `Request to ${path} failed with status ${response.status}`;
    throw new ApiError(error?.message ?? fallback, { status: response.status, code: error?.code ?? 'HTTP_ERROR' });
  }
  return body.data;
}

const getJson = (path, fetchImpl) => request(path, fetchImpl);
const postJson = (path, payload, fetchImpl) => request(path, fetchImpl, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});

export const getHealth = (fetchImpl = fetch) => getJson('/api/health', fetchImpl).then((data) => ({ success: true, data }));

export const getCatalog = (fetchImpl = fetch) => getJson('/api/catalog', fetchImpl);

/** Returns { design, revision } for the predefined basic wardrobe. */
export const getDefaultDesign = (fetchImpl = fetch) => getJson('/api/designs/default', fetchImpl);

/** One agent turn: { messages: [{role, text}], design, revision } -> { reply, proposal|null }. */
export const sendChat = (payload, fetchImpl = fetch) => postJson('/api/chat', payload, fetchImpl);

/** Speech to text: a recorded audio Blob -> { text }. `language` only localizes server errors. */
export const transcribe = (blob, language, fetchImpl = fetch) => request(
  `/api/voice/transcribe?language=${encodeURIComponent(language)}`,
  fetchImpl,
  { method: 'POST', headers: { 'Content-Type': blob.type.split(';')[0] || 'audio/webm' }, body: blob },
);

/** POST JSON, get a binary Blob back (errors still come as the JSON envelope). */
async function postForBlob(path, payload, fetchImpl) {
  if (!API_BASE_URL) throw new Error('The API base URL is not configured');
  let response;
  try {
    response = await fetchImpl(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError('Could not reach the design service.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.error?.message ?? `Request to ${path} failed with status ${response.status}`, {
      status: response.status,
      code: body?.error?.code ?? 'HTTP_ERROR',
    });
  }
  return response.blob();
}

/** Text to speech: { text, language, signature } -> an audio/mpeg Blob (signature = the chat replySignature). */
export const fetchSpeech = (payload, fetchImpl = fetch) => postForBlob('/api/voice/speech', payload, fetchImpl);

/**
 * Design summary PDF for the carpenter:
 * { design, revision, language, preferences, frontImage?, includeSummary? } -> an application/pdf Blob.
 */
export const fetchSpecPdf = (payload, fetchImpl = fetch) => postForBlob('/api/spec/pdf', payload, fetchImpl);

/** Apply a signed proposal: { design, revision, proposal } -> { design, revision }. 409 = stale. */
export const applyProposal = (payload, fetchImpl = fetch) => postJson('/api/proposals/apply', payload, fetchImpl);
