import { expect, openDesigner, test } from './fixtures.js';

// Design summary PDF for the carpenter. The network edge is mocked; the PDF itself is covered by pytest.

const ok = (data) => ({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data }) });

async function mockSpec(page) {
  const calls = { spec: [] };
  await page.route('**/api/health', (route) => route.fulfill(ok({ status: 'ok', env: 'e2e', agent: true })));
  await page.route('**/api/spec/pdf', (route) => {
    calls.spec.push(route.request().postDataJSON());
    return route.fulfill({ status: 200, contentType: 'application/pdf', body: Buffer.from('%PDF-1.7 test') });
  });
  // Headless Chromium: no share sheet, so the PDF is downloaded (the fallback path).
  await page.addInitScript(() => { delete Navigator.prototype.share; delete Navigator.prototype.canShare; });
  return calls;
}

test.describe('design summary PDF', () => {
  test('the dialog sends the committed design, the chat language and only the filled answers, then downloads', async ({ page }) => {
    const calls = await mockSpec(page);
    await openDesigner(page);
    await page.getByTestId('chat-spec').click();
    const dialog = page.getByTestId('spec-dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute('dir', 'rtl');
    await expect(dialog).toContainText('לא שרטוט ייצור');

    await page.getByTestId('spec-use').selectOption('kids');
    await page.getByTestId('spec-location').fill('  נישה בחדר הילדים ');
    await page.getByTestId('spec-name').fill('דנה');
    const download = page.waitForEvent('download');
    await page.getByTestId('spec-create').click();
    expect((await download).suggestedFilename()).toBe('banai-design-r1.pdf');
    await expect(page.getByTestId('spec-status')).toContainText('המסמך הורד');

    const [body] = calls.spec;
    expect(body.language).toBe('he');
    expect(body.revision).toBe(1);
    expect(body.preferences).toEqual({ intendedUse: 'kids', location: 'נישה בחדר הילדים', name: 'דנה' });
    expect(body.frontImage.startsWith('data:image/png;base64,')).toBe(true);
    expect(body.design.dimensions).toEqual({ width: 2000, height: 2400, depth: 600 });
  });

  test('follows the English chat language', async ({ page }) => {
    const calls = await mockSpec(page);
    await openDesigner(page);
    await page.getByTestId('chat-language-en').click();
    await page.getByTestId('chat-spec').click();
    await expect(page.getByTestId('spec-dialog')).toHaveAttribute('dir', 'ltr');
    await expect(page.getByTestId('spec-dialog')).toContainText('not a manufacturing drawing');
    const download = page.waitForEvent('download');
    await page.getByTestId('spec-create').click();
    await download;
    expect(calls.spec[0].language).toBe('en');
    expect(calls.spec[0].preferences).toEqual({});
  });
});
