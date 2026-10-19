import { expect, openDesigner, test } from './fixtures.js';

// Voice end to end with Chromium's fake microphone. The network edge is mocked (no OpenAI calls):
// the transcript must go through the normal chat turn and still need Confirm.

const ok = (data) => ({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data }) });

async function mockVoice(page) {
  const calls = { transcribe: [], transcribeUrls: [], chat: [], speech: [] };
  await page.route('**/api/health', (route) => route.fulfill(ok({ status: 'ok', env: 'e2e', agent: true })));
  await page.route('**/api/voice/transcribe**', (route) => {
    calls.transcribe.push(route.request().headers()['content-type']);
    calls.transcribeUrls.push(route.request().url());
    return route.fulfill(ok({ text: 'make it shallower' }));
  });
  await page.route('**/api/chat', (route) => {
    calls.chat.push(route.request().postDataJSON());
    return route.fulfill(ok({
      reply: 'Sure! Here is my proposal.',
      replySignature: 'c'.repeat(64),
      proposal: {
        proposalId: 'prp_0123456789abcdef', baseRevision: 1, baseHash: 'a'.repeat(64),
        ops: [{ op: 'update_dimensions', depth: 550 }], signature: 'b'.repeat(64),
        summary: 'Makes the wardrobe shallower.', changes: [{ title: 'Depth', detail: '60.0 cm to 55.0 cm' }],
      },
    }));
  });
  await page.route('**/api/voice/speech', (route) => {
    calls.speech.push(route.request().postDataJSON());
    return route.fulfill({ status: 200, contentType: 'audio/mpeg', body: Buffer.from('') });
  });
  await page.route('**/api/proposals/apply', (route) => {
    const body = route.request().postDataJSON();
    const design = structuredClone(body.design);
    design.dimensions.depth = 550;
    return route.fulfill(ok({ design, revision: body.revision + 1 }));
  });
  return calls;
}

const depth = (page) => page.evaluate(() => window.__banai.store.getState().design.dimensions.depth);

test.describe('voice', () => {
  // The mocked speech is an empty body, so Chrome logs a failed media load when it tries to play it.
  test.use({ allowedConsoleErrors: [/ERR_REQUEST_RANGE_NOT_SATISFIABLE/] });

  test('speaking sends the transcript as a chat message; the proposal still needs Confirm', async ({ page }) => {
    const calls = await mockVoice(page);
    await openDesigner(page);
    const mic = page.getByTestId('chat-mic');

    await mic.click();
    await expect(mic).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('chat-hint')).toContainText('מקליט');
    await page.waitForTimeout(600); // record a little of the fake tone
    await mic.click();

    await expect(page.getByTestId('proposal-card')).toContainText('60.0 cm to 55.0 cm');
    expect(calls.transcribe[0]).toBe('audio/webm');
    expect(calls.chat[0].messages.at(-1)).toEqual({ role: 'user', text: 'make it shallower' });
    expect(new URL(calls.transcribeUrls[0]).searchParams.get('language')).toBe('he'); // the selected language is the hint
    expect(calls.chat[0].language).toBe('he'); // English speech, Hebrew selected: the reply stays Hebrew
    await expect(page.getByTestId('chat-language-he')).toHaveAttribute('aria-pressed', 'true');
    await expect(mic).toHaveAttribute('aria-pressed', 'false');
    expect(await depth(page)).toBe(600); // nothing applied by voice alone

    await page.getByTestId('proposal-confirm').click();
    await expect.poll(() => depth(page)).toBe(550);
  });

  test('read aloud is off by default; when on, the next reply is spoken with an AI-voice notice', async ({ page }) => {
    const calls = await mockVoice(page);
    await openDesigner(page);
    const toggle = page.getByTestId('chat-read-aloud');
    await expect(toggle).toHaveAttribute('aria-pressed', 'false');

    await page.getByTestId('chat-input').fill('make it shallower');
    await page.getByTestId('chat-send').click();
    await expect(page.getByTestId('proposal-card')).toBeVisible();
    expect(calls.speech).toHaveLength(0);

    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('chat-hint')).toContainText('AI'); // the AI-voice notice, in the selected language
    await page.getByTestId('proposal-cancel').click();
    await page.getByTestId('chat-input').fill('and make it white');
    await page.getByTestId('chat-send').click();
    await expect.poll(() => calls.speech.length).toBe(1);
    expect(calls.speech[0]).toEqual({ text: 'Sure! Here is my proposal.', language: 'he', signature: 'c'.repeat(64) }); // the selected language

    await page.reload(); // read-aloud is never restored: it starts off on every visit
    await page.getByTestId('entry-basic').click();
    await expect(page.getByTestId('chat-read-aloud')).toHaveAttribute('aria-pressed', 'false');
  });
});
