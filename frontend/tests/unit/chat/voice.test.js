import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchSpeech, transcribe } from '../../../src/api/client.js';
import { createSpeaker, MAX_SPEECH_CHARS, readAloudPreference, startRecording } from '../../../src/chat/voice.js';
import { STRINGS } from '../../../src/chat/i18n.js';

class FakeRecorder {
  static isTypeSupported = (type) => type === 'audio/webm;codecs=opus';

  constructor(stream, options) {
    this.stream = stream;
    this.options = options;
    this.mimeType = options?.mimeType ?? '';
    this.state = 'inactive';
    this.listeners = {};
    FakeRecorder.last = this;
  }

  addEventListener(name, fn) { this.listeners[name] = fn; }

  start() { this.state = 'recording'; }

  stop() {
    this.state = 'inactive';
    this.listeners.dataavailable({ data: new Blob(['abc']) });
    this.listeners.stop();
  }
}

const fakeMedia = () => {
  const track = { stop: vi.fn() };
  return { track, media: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [track] }) } };
};

afterEach(() => vi.useRealTimers());

describe('startRecording', () => {
  it('records opus webm and releases the microphone on stop', async () => {
    const { media, track } = fakeMedia();
    const { stop, done } = await startRecording({ media, Recorder: FakeRecorder });
    expect(media.getUserMedia).toHaveBeenCalledWith({ audio: true });
    expect(FakeRecorder.last.mimeType).toBe('audio/webm;codecs=opus');
    expect(FakeRecorder.last.options.audioBitsPerSecond).toBe(32000);
    stop();
    const blob = await done;
    expect(blob.type).toBe('audio/webm');
    expect(blob.size).toBe(3);
    expect(track.stop).toHaveBeenCalled();
  });

  it('stops by itself after the time limit', async () => {
    vi.useFakeTimers();
    const { media } = fakeMedia();
    const { done } = await startRecording({ media, Recorder: FakeRecorder, maxMs: 1000 });
    vi.advanceTimersByTime(1000);
    await expect(done).resolves.toBeInstanceOf(Blob);
  });

  it('rejects when the microphone is not allowed', async () => {
    const media = { getUserMedia: vi.fn().mockRejectedValue(new Error('NotAllowedError')) };
    await expect(startRecording({ media, Recorder: FakeRecorder })).rejects.toThrow();
  });
});

describe('voice api', () => {
  it('posts raw audio with its type (no codec params) and unwraps the text', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true, data: { text: 'hi' } }) });
    await expect(transcribe(new Blob(['x'], { type: 'audio/webm;codecs=opus' }), 'en', fetchImpl)).resolves.toEqual({ text: 'hi' });
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/voice/transcribe?language=en');
    expect(init.headers['Content-Type']).toBe('audio/webm');
  });

  it('returns the speech blob, and the server message on errors', async () => {
    const audio = new Blob(['mp3']);
    await expect(fetchSpeech({ text: 'hi', language: 'en' }, vi.fn().mockResolvedValue({ ok: true, blob: async () => audio }))).resolves.toBe(audio);
    const failing = vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ success: false, error: { code: 'AGENT_UNAVAILABLE', message: 'Not configured' } }) });
    await expect(fetchSpeech({ text: 'hi' }, failing)).rejects.toMatchObject({ status: 503, code: 'AGENT_UNAVAILABLE', message: 'Not configured' });
  });
});

describe('createSpeaker', () => {
  const urls = { createObjectURL: vi.fn(() => 'blob:1'), revokeObjectURL: vi.fn() };

  it('plays signed replies, stops the previous one, and stays silent without a signature or over the limit', async () => {
    const played = [];
    class FakeAudio {
      constructor(src) { this.src = src; this.pause = vi.fn(); played.push(this); }

      play() { return Promise.resolve(); }
    }
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['mp3']) });
    const speaker = createSpeaker({ fetchImpl, AudioImpl: FakeAudio, urls });
    await speaker.speak('x'.repeat(MAX_SPEECH_CHARS + 1), 'en', 'sig');
    await speaker.speak('unsigned', 'en');
    expect(fetchImpl).not.toHaveBeenCalled();
    await speaker.speak('first', 'en', 'sig1');
    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toEqual({ text: 'first', language: 'en', signature: 'sig1' });
    await speaker.speak('second', 'en', 'sig2');
    expect(played[0].pause).toHaveBeenCalled();
    expect(urls.revokeObjectURL).toHaveBeenCalledWith('blob:1');
    expect(played).toHaveLength(2);
  });
});

describe('readAloudPreference', () => {
  const memory = (initial = {}) => {
    const store = new Map(Object.entries(initial));
    return { store, getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k) };
  };

  it('is off on every visit and turns on only when set', () => {
    const storage = memory();
    const pref = readAloudPreference(storage);
    expect(pref.get()).toBe(false);
    pref.set(true); // the customer clicked the toggle
    expect(pref.get()).toBe(true);
    expect(readAloudPreference(storage).get()).toBe(false); // the next visit starts off again
  });

  it('ignores and clears an old saved "on" (it kept read-aloud on in later sessions)', () => {
    const storage = memory({ 'banai.chat.readAloud': 'on' });
    expect(readAloudPreference(storage).get()).toBe(false);
    expect(storage.store.has('banai.chat.readAloud')).toBe(false);
  });

  it('survives blocked storage', () => {
    const blocked = () => { throw new Error('blocked'); };
    const pref = readAloudPreference({ getItem: blocked, setItem: blocked, removeItem: blocked });
    expect(pref.get()).toBe(false);
    pref.set(true);
    expect(pref.get()).toBe(true);
  });
});

describe('voice strings', () => {
  it('exist in both languages and disclose the AI voice', () => {
    for (const key of ['mic', 'micStop', 'recording', 'transcribing', 'micDenied', 'voiceError', 'readAloud', 'readAloudOn']) {
      expect(STRINGS.he[key], key).toBeTruthy();
      expect(STRINGS.en[key], key).toBeTruthy();
    }
    expect(STRINGS.en.readAloud).toContain('AI');
    expect(STRINGS.he.readAloud).toContain('AI');
  });
});
