// "Summary for the carpenter" dialog: optional closing questions, then a PDF of the confirmed design
// (built on the server) that is shared or downloaded. It is a visual design draft, never a
// manufacturing drawing, and the dialog says so before anything is created.
import { el } from '../editor/fields.js';
import { createDialog } from '../ui/dialog.js';
import { stringsFor } from '../chat/i18n.js';
import { fetchSpecPdf } from '../api/client.js';
import { INTENDED_USES, SPEC_LIMITS, specFilename, specRequest } from './specRequest.js';
import { shareOrDownload } from './share.js';

let fieldCount = 0;

function field(label, control) {
  fieldCount += 1;
  const id = `spec-field-${fieldCount}`;
  control.id = id;
  return el('div', { className: 'field' }, [el('label', { className: 'field__label', text: label, attrs: { for: id } }), control]);
}

/**
 * getState: () => { design, revision } of the committed design; getLanguage: () => 'he' | 'en';
 * captureFront: () => PNG data URL (or null). `fetchPdf` / `share` are injectable for tests.
 */
export function createSpecDialog({ getState, getLanguage, captureFront, fetchPdf = fetchSpecPdf, share = shareOrDownload }) {
  let current = null;

  function open() {
    current?.element.remove();
    const language = getLanguage();
    const t = stringsFor(language).spec;
    const use = el('select', { className: 'field__input' }, [
      el('option', { text: t.useNone, attrs: { value: '' } }),
      ...INTENDED_USES.map((value) => el('option', { text: t.uses[value], attrs: { value } })),
    ]);
    const text = (key, hint) => {
      const input = el(key === 'requests' ? 'textarea' : 'input', {
        className: 'field__input',
        attrs: { maxlength: String(SPEC_LIMITS[key]), dir: 'auto', ...(key === 'requests' ? { rows: '3' } : { type: 'text' }), ...(hint ? { placeholder: hint } : {}) },
      });
      input.dataset.testid = `spec-${key}`;
      return input;
    };
    const inputs = { location: text('location', t.locationHint), timeline: text('timeline'), requests: text('requests'), name: text('name') };
    use.dataset.testid = 'spec-use';
    const status = el('p', { className: 'spec__status', attrs: { role: 'status', 'aria-live': 'polite' } });
    status.dataset.testid = 'spec-status';

    const create = el('button', { className: 'btn btn--primary', text: t.create, attrs: { type: 'button' } });
    create.dataset.testid = 'spec-create';
    const cancel = el('button', { className: 'btn', text: t.cancel, attrs: { type: 'button' } });

    const dialog = createDialog({
      title: t.title,
      labelId: 'spec-dialog-title',
      testId: 'spec-dialog',
      body: [
        el('p', { text: t.intro }),
        el('p', { className: 'spec__disclaimer', text: t.disclaimer }),
        field(t.use, use),
        field(t.location, inputs.location),
        field(t.timeline, inputs.timeline),
        field(t.requests, inputs.requests),
        field(t.name, inputs.name),
        el('p', { className: 'spec__privacy', text: t.privacy }),
        status,
      ],
      actions: [cancel, create],
    });
    dialog.element.setAttribute('dir', stringsFor(language).dir);
    dialog.element.setAttribute('lang', language);
    cancel.addEventListener('click', dialog.close);
    dialog.element.addEventListener('close', () => dialog.element.remove());

    create.addEventListener('click', async () => {
      create.disabled = true;
      status.textContent = t.working;
      const { design, revision } = getState();
      const form = { intendedUse: use.value, ...Object.fromEntries(Object.entries(inputs).map(([key, input]) => [key, input.value])) };
      let frontImage = null;
      try {
        frontImage = captureFront();
      } catch {
        // no image: the PDF is still complete without it
      }
      try {
        const blob = await fetchPdf(specRequest({ design, revision, language, form, frontImage }));
        const result = await share(blob, specFilename(revision), { title: t.title });
        // The dialog stays open with the result, so the customer sees what happened.
        status.textContent = { shared: t.shared, downloaded: t.downloaded }[result] ?? '';
      } catch (error) {
        status.textContent = error?.status ? error.message : t.failed;
      } finally {
        create.disabled = false;
      }
    });

    current = dialog;
    dialog.open();
    return dialog;
  }

  return { open };
}
