import { expect, openDesigner, test } from './fixtures.js';

// The agent flow end to end in the browser. The network edge is mocked (the E2E backend has no
// OpenAI key, so it never calls OpenAI); the signed-proposal protocol itself is covered by pytest.

const ok = (data) => ({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data }) });

async function mockAgent(page, { applyStatus = 200 } = {}) {
  const calls = { chat: [], apply: [] };
  await page.route('**/api/health', (route) => route.fulfill(ok({ status: 'ok', env: 'e2e', agent: true })));
  await page.route('**/api/chat', async (route) => {
    const body = route.request().postDataJSON();
    calls.chat.push(body);
    await new Promise((resolve) => setTimeout(resolve, 400)); // long enough to see the typing indicator
    const english = body.language === 'en'; // like the real agent, reply in the chosen language
    await route.fulfill(ok({
      reply: english ? 'Sure! Here is my proposal.' : 'אפשר! הנה ההצעה שלי.',
      proposal: {
        proposalId: 'prp_0123456789abcdef', baseRevision: body.revision, baseHash: 'a'.repeat(64),
        ops: [{ op: 'update_dimensions', depth: 550 }], signature: 'b'.repeat(64),
        summary: 'Makes the wardrobe shallower.', changes: [{ title: 'Depth', detail: '60.0 cm to 55.0 cm' }],
      },
    }));
  });
  await page.route('**/api/proposals/apply', async (route) => {
    const body = route.request().postDataJSON();
    calls.apply.push(body);
    if (applyStatus !== 200) {
      await route.fulfill({ status: applyStatus, contentType: 'application/json', body: JSON.stringify({ success: false, error: { code: 'STALE', message: 'Design changed' } }) });
      return;
    }
    const design = structuredClone(body.design);
    design.dimensions.depth = 550;
    await route.fulfill(ok({ design, revision: body.revision + 1 }));
  });
  return calls;
}

const revision = (page) => page.evaluate(() => window.__banai.store.getState().revision);
const depth = (page) => page.evaluate(() => window.__banai.store.getState().design.dimensions.depth);

test.describe('AI designer (agent connected)', () => {
  test('a message gets a reply and a proposal; Confirm applies it to the design', async ({ page }) => {
    const calls = await mockAgent(page);
    await openDesigner(page);
    await expect(page.locator('.chat__status--online')).toHaveText('מחובר');

    await page.getByTestId('chat-input').fill('תעשה אותו פחות עמוק, 55 ס"מ');
    await page.getByTestId('chat-send').click();
    await expect(page.getByTestId('chat-typing')).toBeVisible();
    await expect(page.getByTestId('chat-send')).toBeDisabled();

    const messages = page.getByTestId('chat-messages');
    await expect(messages).toContainText('אפשר! הנה ההצעה שלי.');
    await expect(page.getByTestId('chat-typing')).toBeHidden();
    await expect(page.getByTestId('proposal-card')).toContainText('60.0 cm to 55.0 cm');
    expect(calls.chat[0].messages).toEqual([{ role: 'user', text: 'תעשה אותו פחות עמוק, 55 ס"מ' }]);
    expect(calls.chat[0].revision).toBe(1);
    expect(await depth(page)).toBe(600); // nothing applied before Confirm

    await page.getByTestId('proposal-confirm').click();
    await expect(messages).toContainText('השינויים הוחלו. העיצוב שלך עודכן.');
    await expect(page.getByTestId('proposal-card')).toHaveCount(0);
    expect(await depth(page)).toBe(550);
    expect(await revision(page)).toBe(2);
    expect(calls.apply[0].proposal.signature).toBe('b'.repeat(64)); // sent back unchanged
    await expect(page.getByText('D 55.0 cm', { exact: true })).toBeVisible();
  });

  test('switching to English localizes the chat and asks the agent for English', async ({ page }) => {
    const calls = await mockAgent(page);
    await openDesigner(page);
    const panel = page.locator('#chat-panel');
    await expect(panel).toHaveAttribute('dir', 'rtl');
    await expect(page.getByTestId('chat-welcome')).toContainText('מה נעצב היום?');

    await page.getByTestId('chat-language-en').click();
    await expect(panel).toHaveAttribute('dir', 'ltr');
    await expect(page.getByTestId('chat-language-en')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('chat-welcome')).toContainText('What shall we design today?');
    await expect(page.getByTestId('suggestion').first()).toContainText('240 cm wide');
    await expect(page.locator('.chat__status--online')).toHaveText('Online');

    await page.getByTestId('chat-input').fill('make it shallower');
    await page.getByTestId('chat-send').click();
    await expect(page.getByTestId('proposal-card')).toContainText('Proposed changes');
    await expect(page.getByTestId('proposal-confirm')).toContainText('Confirm');
    expect(calls.chat[0].language).toBe('en');

    await page.reload(); // the choice is remembered
    await page.getByTestId('entry-basic').click();
    await expect(page.locator('#chat-panel')).toHaveAttribute('dir', 'ltr');
  });

  test('the selected language is the only reply language, whatever is written', async ({ page }) => {
    const calls = await mockAgent(page);
    await openDesigner(page);
    await expect(page.getByTestId('chat-language-he')).toHaveAttribute('aria-pressed', 'true'); // default עברית
    await expect(page.getByTestId('chat-language-he')).toHaveText('עברית');
    await expect(page.getByTestId('chat-language-en')).toHaveText('English');

    // Hebrew selected + an English message: the chat stays Hebrew and asks for Hebrew.
    await page.getByTestId('chat-input').fill('make it shallower please');
    await page.getByTestId('chat-send').click();
    await expect(page.locator('.chat__bubble--assistant:not(.chat__typing)').last()).toHaveText('אפשר! הנה ההצעה שלי.');
    await expect(page.getByTestId('chat-language-he')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#chat-panel')).toHaveAttribute('dir', 'rtl');
    await expect(page.getByTestId('chat-input')).toHaveValue('');
    expect(calls.chat[0].language).toBe('he');

    // English selected + a Hebrew message: English.
    await page.getByTestId('proposal-cancel').click();
    await page.getByTestId('chat-language-en').click();
    await page.getByTestId('chat-input').fill('ותעשה אותו לבן');
    await page.getByTestId('chat-send').click();
    await expect(page.locator('.chat__bubble--assistant:not(.chat__typing)').last()).toHaveText('Sure! Here is my proposal.');
    await expect(page.getByTestId('chat-language-en')).toHaveAttribute('aria-pressed', 'true');
    expect(calls.chat[1].language).toBe('en');
    expect(calls.chat).toHaveLength(2); // each message sent exactly once
  });

  test('switching language never changes what is already on screen', async ({ page }) => {
    await mockAgent(page);
    await openDesigner(page);
    const bubbles = () => page.locator('.chat__bubble:not(.chat__typing)').evaluateAll((nodes) => nodes.map((n) => ({ text: n.textContent, dir: n.getAttribute('dir') })));
    const send = async (text) => {
      const count = await page.locator('.chat__bubble--assistant:not(.chat__typing)').count();
      await page.getByTestId('chat-input').fill(text);
      await page.getByTestId('chat-send').click();
      await expect(page.locator('.chat__bubble--assistant:not(.chat__typing)')).toHaveCount(count + 1);
    };

    // 1. A Hebrew conversation.
    await send('תעשה אותו פחות עמוק');
    const hebrewTurn = await bubbles();
    expect(hebrewTurn.at(-1)).toEqual({ text: 'אפשר! הנה ההצעה שלי.', dir: 'rtl' });
    await expect(page.getByTestId('proposal-card')).toContainText('שינויים מוצעים');

    // 2. Switch to English: the Hebrew messages and the open Hebrew card stay exactly as they were.
    await page.getByTestId('chat-language-en').click();
    await expect(page.locator('#chat-panel')).toHaveAttribute('dir', 'ltr');
    expect(await bubbles()).toEqual(hebrewTurn);
    await expect(page.getByTestId('proposal-card')).toContainText('שינויים מוצעים');
    await expect(page.getByTestId('proposal-confirm')).toContainText('אישור');
    await expect(page.getByTestId('proposal-card')).toHaveAttribute('dir', 'rtl');

    // 3. Keep talking in English: only the new messages are English.
    await page.getByTestId('proposal-cancel').click();
    await send('make it shallower');
    const mixed = await bubbles();
    expect(mixed.slice(0, hebrewTurn.length)).toEqual(hebrewTurn);
    expect(mixed.at(-1)).toEqual({ text: 'Sure! Here is my proposal.', dir: 'ltr' });
    await expect(page.getByTestId('proposal-card')).toContainText('Proposed changes');

    // 4. Back to Hebrew: the English messages and the English card stay English.
    await page.getByTestId('chat-language-he').click();
    await expect(page.locator('#chat-panel')).toHaveAttribute('dir', 'rtl');
    expect(await bubbles()).toEqual(mixed);
    await expect(page.getByTestId('proposal-card')).toContainText('Proposed changes');
    await expect(page.getByTestId('proposal-confirm')).toContainText('Confirm');
  });

  test.describe('when the design changed on the server side', () => {
    test.use({ allowedConsoleErrors: [/status of 409 \(Conflict\)/] });

    test('a stale proposal is refused by the server and nothing changes', async ({ page }) => {
      await mockAgent(page, { applyStatus: 409 });
      await openDesigner(page);
      await page.getByTestId('chat-input').fill('תעשה אותו פחות עמוק');
      await page.getByTestId('chat-send').click();
      await expect(page.getByTestId('proposal-card')).toBeVisible();
      await page.getByTestId('proposal-confirm').click();
      await expect(page.getByTestId('chat-messages')).toContainText('העיצוב השתנה. בקש מהמעצב הצעה חדשה.');
      expect(await depth(page)).toBe(600);
      expect(await revision(page)).toBe(1);
    });
  });
});
