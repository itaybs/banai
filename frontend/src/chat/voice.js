// Voice for the chat: record the customer's speech, and play the designer's replies aloud.
// Recording only produces audio; the transcript is sent as a normal chat message, so a voice
// request still ends in a proposal the customer must confirm.
import { fetchSpeech } from '../api/client.js';

export const MAX_RECORDING_MS = 60_000; // the backend caps uploads at 1 MB
export const MAX_SPEECH_CHARS = 1000; // mirrors the backend limit
const BITS_PER_SECOND = 32_000; // plenty for speech; 60 s stays ~240 KB, well under the 1 MB cap
const PREFERRED_TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'];
const READ_ALOUD_KEY = 'banai.chat.readAloud';

export const canRecord = () => typeof globalThis.MediaRecorder === 'function' && Boolean(globalThis.navigator?.mediaDevices?.getUserMedia);

/**
 * Starts recording the microphone. Resolves to { stop, done }: `done` resolves to the audio Blob
 * once recording stops (by `stop()` or after `maxMs`). Rejects if the microphone is not allowed.
 */
export async function startRecording({
  media = globalThis.navigator?.mediaDevices,
  Recorder = globalThis.MediaRecorder,
  maxMs = MAX_RECORDING_MS,
} = {}) {
  const stream = await media.getUserMedia({ audio: true });
  const mimeType = PREFERRED_TYPES.find((type) => Recorder.isTypeSupported?.(type));
  const recorder = new Recorder(stream, { audioBitsPerSecond: BITS_PER_SECOND, ...(mimeType && { mimeType }) });
  const chunks = [];
  let timer = null;
  recorder.addEventListener('dataavailable', (event) => {
    if (event.data?.size) chunks.push(event.data);
  });
  const done = new Promise((resolve) => {
    recorder.addEventListener('stop', () => {
      clearTimeout(timer);
      stream.getTracks().forEach((track) => track.stop()); // releases the microphone indicator
      const type = (recorder.mimeType || mimeType || 'audio/webm').split(';')[0];
      resolve(new Blob(chunks, { type }));
    });
  });
  const stop = () => {
    if (recorder.state !== 'inactive') recorder.stop();
  };
  recorder.start();
  timer = setTimeout(stop, maxMs);
  return { stop, done };
}

/** Plays replies one at a time; a new reply (or stop()) cuts off the previous one. */
export function createSpeaker({ fetchImpl = fetch, AudioImpl = globalThis.Audio, urls = URL } = {}) {
  let current = null;
  let url = null;
  let turn = 0;
  const stop = () => {
    turn += 1;
    current?.pause();
    if (url) urls.revokeObjectURL(url);
    current = null;
    url = null;
  };
  return {
    /** `signature` is the reply's server signature: only the agent's own replies can be spoken. */
    async speak(text, language, signature) {
      stop();
      if (!signature || text.length > MAX_SPEECH_CHARS) return; // unsigned or too long: stay silent
      const mine = turn;
      const blob = await fetchSpeech({ text, language, signature }, fetchImpl);
      if (mine !== turn) return; // a newer reply (or stop) arrived while this one was loading
      url = urls.createObjectURL(blob);
      current = new AudioImpl(url);
      await current.play();
    },
    stop,
  };
}

/**
 * Read-aloud: OFF on every visit, and on only after the customer turns it on (it is never restored).
 * A saved "on" from older versions kept it on in later sessions after one stray click, so the old
 * stored value is removed.
 */
export function readAloudPreference(storage = globalThis.localStorage) {
  let on = false;
  try {
    storage?.removeItem(READ_ALOUD_KEY);
  } catch {
    // blocked storage: nothing was saved
  }
  return {
    get: () => on,
    set(next) {
      on = Boolean(next);
    },
  };
}
