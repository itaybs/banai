import { describe, expect, it, vi } from 'vitest';
import { fetchSpecPdf } from '../../../src/api/client.js';
import { STRINGS } from '../../../src/chat/i18n.js';
import { isTouchDevice, shareOrDownload } from '../../../src/spec/share.js';
import { INTENDED_USES, SPEC_LIMITS, specFilename, specPreferences, specRequest } from '../../../src/spec/specRequest.js';
import { CAPTURE_HEIGHT, CAPTURE_WIDTH, frontView } from '../../../src/viewer/capture.js';

describe('spec request', () => {
  it('keeps only the answers the customer gave, trimmed and within the limits', () => {
    expect(specPreferences({})).toEqual({});
    expect(specPreferences({ intendedUse: '', location: '   ', name: '' })).toEqual({});
    expect(specPreferences({ intendedUse: 'kids', location: '  חדר   ילדים ', requests: 'x'.repeat(600) })).toEqual({
      intendedUse: 'kids', location: 'חדר ילדים', requests: 'x'.repeat(SPEC_LIMITS.requests),
    });
    expect(specPreferences({ intendedUse: 'budget' })).toEqual({}); // only the known uses
  });

  it('sends the committed design, revision and chat language; no pricing field exists', () => {
    const design = { dimensions: { width: 2000 } };
    expect(specRequest({ design, revision: 4, language: 'he', form: { name: 'דנה' } })).toEqual({
      design, revision: 4, language: 'he', preferences: { name: 'דנה' },
    });
    expect(specRequest({ design, revision: 4, language: 'en', frontImage: 'data:image/png;base64,AA' }).frontImage).toBe('data:image/png;base64,AA');
    expect(Object.keys(SPEC_LIMITS)).not.toContain('budget');
    expect(INTENDED_USES).toEqual(['clothes', 'kids', 'linen', 'mixed']);
    expect(specFilename(4)).toBe('banai-design-r4.pdf');
  });

  it('has every dialog string in both languages, with the disclaimer', () => {
    expect(Object.keys(STRINGS.he.spec).sort()).toEqual(Object.keys(STRINGS.en.spec).sort());
    expect(STRINGS.he.spec.disclaimer).toContain('לא שרטוט ייצור');
    expect(STRINGS.en.spec.disclaimer).toContain('not a manufacturing drawing');
    for (const strings of [STRINGS.he.spec, STRINGS.en.spec]) {
      expect(Object.keys(strings.uses)).toEqual(INTENDED_USES);
    }
  });
});

describe('fetchSpecPdf', () => {
  it('posts JSON to /api/spec/pdf and returns the PDF blob', async () => {
    const pdf = new Blob(['%PDF'], { type: 'application/pdf' });
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, blob: async () => pdf });
    await expect(fetchSpecPdf({ revision: 1 }, fetchImpl)).resolves.toBe(pdf);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/spec/pdf');
    expect(init).toMatchObject({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"revision":1}' });
  });

  it('turns the error envelope into an ApiError with the server message', async () => {
    const failing = vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ success: false, error: { code: 'TEXT_CLAIM', message: 'נא לנסח מחדש.' } }) });
    await expect(fetchSpecPdf({}, failing)).rejects.toMatchObject({ status: 422, code: 'TEXT_CLAIM', message: 'נא לנסח מחדש.' });
  });
});

describe('shareOrDownload', () => {
  const pdf = new Blob(['%PDF'], { type: 'application/pdf' });
  const fakeDoc = () => {
    const link = { click: vi.fn(), remove: vi.fn() };
    return { link, doc: { createElement: vi.fn(() => link), body: { append: vi.fn() } } };
  };
  const urls = { createObjectURL: vi.fn(() => 'blob:1'), revokeObjectURL: vi.fn() };
  const touch = vi.fn((query) => ({ matches: query === '(pointer: coarse)' }));
  const mouse = vi.fn(() => ({ matches: false }));

  it('detects touch devices with (pointer: coarse)', () => {
    expect(isTouchDevice(touch)).toBe(true);
    expect(isTouchDevice(mouse)).toBe(false);
    expect(isTouchDevice(undefined)).toBe(false);
    expect(touch).toHaveBeenCalledWith('(pointer: coarse)');
  });

  it('uses the share sheet on a touch device that can share the file', async () => {
    const nav = { canShare: vi.fn(() => true), share: vi.fn(async () => {}) };
    const { doc, link } = fakeDoc();
    await expect(shareOrDownload(pdf, 'banai-design-r4.pdf', { title: 'T', nav, doc, urls, matchMediaImpl: touch })).resolves.toBe('shared');
    const [{ files, title }] = nav.share.mock.calls[0];
    expect(title).toBe('T');
    expect(files[0]).toMatchObject({ name: 'banai-design-r4.pdf', type: 'application/pdf' });
    expect(link.click).not.toHaveBeenCalled();
  });

  it('downloads on desktop even when the browser could share files', async () => {
    const nav = { canShare: vi.fn(() => true), share: vi.fn(async () => {}) };
    const { doc, link } = fakeDoc();
    await expect(shareOrDownload(pdf, 'a.pdf', { nav, doc, urls, matchMediaImpl: mouse })).resolves.toBe('downloaded');
    expect(nav.share).not.toHaveBeenCalled();
    expect(link.click).toHaveBeenCalledTimes(1);
  });

  it('downloads on a touch device when sharing files is not supported, or sharing fails', async () => {
    for (const nav of [{}, { canShare: () => false, share: vi.fn() }, { canShare: () => true, share: vi.fn(async () => { throw new Error('NotAllowed'); }) }]) {
      const { doc, link } = fakeDoc();
      await expect(shareOrDownload(pdf, 'a.pdf', { nav, doc, urls, matchMediaImpl: touch })).resolves.toBe('downloaded');
      expect(link).toMatchObject({ href: 'blob:1', download: 'a.pdf' });
      expect(link.click).toHaveBeenCalledTimes(1);
    }
  });

  it('reports a cancelled share sheet without downloading', async () => {
    const nav = { canShare: () => true, share: vi.fn(async () => { throw Object.assign(new Error('x'), { name: 'AbortError' }); }) };
    const { doc, link } = fakeDoc();
    await expect(shareOrDownload(pdf, 'a.pdf', { nav, doc, urls, matchMediaImpl: touch })).resolves.toBe('cancelled');
    expect(link.click).not.toHaveBeenCalled();
  });
});

describe('front view capture framing', () => {
  it('looks straight at the centre of the front and fits the whole wardrobe', () => {
    const aspect = CAPTURE_WIDTH / CAPTURE_HEIGHT;
    const { position, target } = frontView({ width: 2000, height: 2400, depth: 600 }, 40, aspect);
    expect(target).toEqual({ x: 1, y: 1.2, z: -0.3 });
    expect(position.x).toBe(1);
    expect(position.y).toBe(1.2);
    const halfHeightSeen = Math.tan((20 * Math.PI) / 180) * position.z; // at the front face (z = 0)
    expect(halfHeightSeen).toBeGreaterThan(1.2);
    expect(halfHeightSeen * aspect).toBeGreaterThan(1);
  });

  it('a wide wardrobe is fitted by its width', () => {
    const aspect = CAPTURE_WIDTH / CAPTURE_HEIGHT;
    const { position } = frontView({ width: 4000, height: 2000, depth: 600 }, 40, aspect);
    const halfWidthSeen = Math.tan((20 * Math.PI) / 180) * aspect * position.z;
    expect(halfWidthSeen).toBeGreaterThan(2);
  });
});
