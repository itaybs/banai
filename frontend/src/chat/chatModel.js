// Pure chat view-model (no DOM). With an `agent` (Phase 5) a sent message goes to the AI designer;
// without one, it gets an honest "not connected" reply. Either way nothing is ever applied to the
// design from here: a proposal only changes the design after the customer confirms it.
//
// A proposal is { id, baseRevision, summary, changes: [{ title, detail }], signed? }. It is kept
// apart from the committed design and is only ever "pending" or "stale" (the design changed after
// it was made). `signed` is the server's signed payload, sent back unchanged on confirm.

import { DEFAULT_LANGUAGE, STRINGS, stringsFor } from './i18n.js';

// Default-language (Hebrew) texts, kept as named exports for callers and tests.
export const NOT_CONNECTED_MESSAGE = STRINGS.he.notConnected;
export const STALE_MESSAGE = STRINGS.he.stale;
export const AGENT_ERROR_MESSAGE = STRINGS.he.agentError;
export const APPLIED_MESSAGE = STRINGS.he.applied;
export const NOT_APPLIED_MESSAGE = STRINGS.he.notApplied;
export const MAX_MESSAGE_LENGTH = 2000;
export const MAX_HISTORY = 30; // mirrors the backend cap on messages per request
export const COUNTER_FROM = 1800; // the composer shows "n / 2000" from here on

/** True when pasting `pastedLength` characters over the selection would pass the message limit (the input cuts it). */
export const pasteOverflows = (valueLength, selectionLength, pastedLength) => valueLength - selectionLength + pastedLength > MAX_MESSAGE_LENGTH;

// Starter prompts shown before the first message (per language in i18n.js). Picking one only fills the composer.
export const SUGGESTIONS = STRINGS.he.suggestions;

/** The history note the model gets for a proposal's outcome, e.g. "[app] applied: Adds a shelf". */
export const appNote = (outcome, summary) => (summary ? `[app] ${outcome}: ${summary}` : `[app] ${outcome}`);

export function proposalStatus(proposal, currentRevision) {
  if (!proposal) return null;
  return proposal.baseRevision === currentRevision ? 'pending' : 'stale';
}

/**
 * Map the server's signed proposal to the view-model shape (the original travels in `signed`).
 * `language` is the language it was written in; the card keeps showing it in that language.
 */
export function fromServerProposal(signed, language = DEFAULT_LANGUAGE) {
  return {
    id: signed.proposalId,
    baseRevision: signed.baseRevision,
    summary: signed.summary,
    changes: signed.changes,
    language,
    signed,
  };
}

/**
 * @param getRevision  () => current committed revision
 * @param agent        optional async ({ messages, language }) => { reply, proposal|null }, where
 *                     messages is the user/assistant history ending with the new customer message
 * @param getLanguage  () => the chat language ('he' | 'en'): the agent replies in it, and so do UI notes
 */
export function createChatModel({ getRevision, agent = null, getLanguage = () => DEFAULT_LANGUAGE }) {
  let nextId = 1;
  let proposal = null;
  let busy = false;
  const messages = [];
  const rejected = new Set(); // ids of customer messages the server refused (4xx): never resent
  const listeners = new Set();
  const notify = () => listeners.forEach((listener) => listener());
  const t = () => stringsFor(getLanguage());
  // Every message remembers the language it was written in, so switching the chat language later
  // never changes how earlier messages look (a Hebrew message stays Hebrew and right-to-left).
  // An agent reply also keeps its server signature, which read-aloud needs (/api/voice/speech).
  // `agentNote` (system notes only) is what the model is told about the note, e.g. which proposal
  // was applied; the note's own text is UI-only.
  const push = (role, text, language = getLanguage(), signature = null, agentNote = null) => {
    messages.push(Object.freeze({ id: nextId, role, text, language, ...(signature && { signature }), ...(agentNote && { agentNote }) }));
    nextId += 1;
  };
  // The model gets the dialogue plus short "[app] applied/cancelled: <summary>" notes, so it knows
  // which proposals were confirmed. Other system notes stay UI-only.
  // A refused message stays visible but is left out, or every later request would be refused too.
  const history = () => messages
    .filter((m) => ((m.role === 'user' || m.role === 'assistant') && !rejected.has(m.id)) || m.agentNote)
    .slice(-MAX_HISTORY)
    .map(({ role, text, agentNote }) => (agentNote ? { role: 'user', text: agentNote } : { role, text }));

  async function ask(messageId) {
    // The reply is written in the language chosen when the message was sent, even if the
    // customer switches language while the designer is still thinking.
    const language = getLanguage();
    busy = true;
    notify();
    try {
      const { reply, replySignature, proposal: signed } = await agent({ messages: history(), language });
      push('assistant', reply, language, replySignature);
      if (signed) proposal = fromServerProposal(signed, language);
    } catch (error) {
      if (error?.status >= 400 && error.status < 500) {
        rejected.add(messageId);
        push('system', stringsFor(language).messageRejected, language);
        return;
      }
      push('system', error?.message && error.status ? error.message : stringsFor(language).agentError, language);
    } finally {
      busy = false;
      notify();
    }
  }

  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getMessages: () => [...messages],
    getProposal: () => proposal,
    getProposalStatus: () => proposalStatus(proposal, getRevision()),
    isBusy: () => busy,
    isConnected: () => agent !== null,

    /**
     * A customer message. Returns { ok } synchronously; with an agent, the reply (and maybe a
     * proposal) arrives later through subscribers. Never touches the design.
     */
    send(rawText) {
      const text = String(rawText ?? '').trim();
      if (!text) return { ok: false, reason: 'empty' };
      if (text.length > MAX_MESSAGE_LENGTH) return { ok: false, reason: 'too-long' };
      if (busy) return { ok: false, reason: 'busy' };
      const messageId = nextId;
      push('user', text);
      if (!agent) {
        push('system', t().notConnected);
        notify();
        return { ok: true };
      }
      // A new request supersedes an unconfirmed proposal.
      proposal = null;
      ask(messageId);
      return { ok: true };
    },

    /** Set by the agent integration (Phase 5) or the dev-only demo. */
    setProposal(next) {
      proposal = next;
      notify();
    },

    /** Cancel never changes the design; it only drops the pending proposal. */
    cancelProposal() {
      if (!proposal) return false;
      const { summary } = proposal;
      proposal = null;
      push('system', t().cancelled, getLanguage(), null, appNote('cancelled', summary));
      notify();
      return true;
    },

    /** Called after the host applied (`applied: true`) or refused the proposal. */
    resolveProposal(message, { applied = false } = {}) {
      const summary = proposal?.summary;
      proposal = null;
      if (message) push('system', message, getLanguage(), null, applied ? appNote('applied', summary) : null);
      notify();
    },
  };
}
