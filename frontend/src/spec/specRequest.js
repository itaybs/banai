// The design summary PDF request, built from the confirmed design and the optional form answers.
// Pure (no DOM), mirrored by the backend's SpecRequest model.

export const SPEC_LIMITS = Object.freeze({ location: 200, timeline: 100, requests: 500, name: 80 });
export const INTENDED_USES = Object.freeze(['clothes', 'kids', 'linen', 'mixed']);

/** Only the fields the customer filled in, trimmed (empty answers are left out). */
export function specPreferences(form) {
  const preferences = {};
  if (INTENDED_USES.includes(form.intendedUse)) preferences.intendedUse = form.intendedUse;
  for (const [key, max] of Object.entries(SPEC_LIMITS)) {
    const value = String(form[key] ?? '').replace(/\s+/g, ' ').trim().slice(0, max);
    if (value) preferences[key] = value;
  }
  return preferences;
}

/** The request body: the confirmed design and revision (never a pending proposal), the chat language. */
export function specRequest({ design, revision, language, form = {}, frontImage = null }) {
  return {
    design,
    revision,
    language,
    preferences: specPreferences(form),
    ...(frontImage ? { frontImage } : {}),
  };
}

export const specFilename = (revision) => `banai-design-r${revision}.pdf`;
