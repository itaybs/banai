// Hands the design summary PDF to the customer: on touch devices (phones, tablets) the device's share
// sheet (WhatsApp, email…), on desktop a normal download — desktop browsers that can share files open
// the operating system's share window, which is not what people expect there. The app sends nothing.

/** True on touch-first devices, where the share sheet is the natural way to send a file. */
export const isTouchDevice = (matchMediaImpl = globalThis.matchMedia) => Boolean(matchMediaImpl?.('(pointer: coarse)')?.matches);

/**
 * Resolves to 'shared', 'downloaded' or 'cancelled' (the customer closed the share sheet).
 * `nav` / `doc` / `urls` / `matchMediaImpl` are injectable for tests.
 */
export async function shareOrDownload(blob, filename, {
  title = filename, nav = globalThis.navigator, doc = globalThis.document, urls = URL, matchMediaImpl = globalThis.matchMedia,
} = {}) {
  const file = new File([blob], filename, { type: 'application/pdf' });
  if (isTouchDevice(matchMediaImpl) && typeof nav?.share === 'function' && nav.canShare?.({ files: [file] })) {
    try {
      await nav.share({ files: [file], title });
      return 'shared';
    } catch (error) {
      if (error?.name === 'AbortError') return 'cancelled';
      // Sharing failed for another reason (e.g. not allowed here): fall back to a download.
    }
  }
  const url = urls.createObjectURL(blob);
  const link = doc.createElement('a');
  link.href = url;
  link.download = filename;
  link.rel = 'noopener';
  doc.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => urls.revokeObjectURL(url), 1000);
  return 'downloaded';
}
