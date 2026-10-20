// Hands the design summary PDF to the customer: the device's share sheet (WhatsApp, email…) where the
// browser can share files, otherwise a normal download. The app itself never sends anything.

/**
 * Resolves to 'shared', 'downloaded' or 'cancelled' (the customer closed the share sheet).
 * `nav` / `doc` / `urls` are injectable for tests.
 */
export async function shareOrDownload(blob, filename, { title = filename, nav = globalThis.navigator, doc = globalThis.document, urls = URL } = {}) {
  const file = new File([blob], filename, { type: 'application/pdf' });
  if (typeof nav?.share === 'function' && nav.canShare?.({ files: [file] })) {
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
