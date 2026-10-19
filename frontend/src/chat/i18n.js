// Chat panel strings in Hebrew and English. The customer picks the language above the chat
// (default עברית, remembered per browser); it is the only reply language, whatever a message is
// written in, and the chat UI, notes, errors and read-aloud all follow it.

export const LANGUAGES = Object.freeze(['he', 'en']);
export const DEFAULT_LANGUAGE = 'he';
const STORAGE_KEY = 'banai.chat.language';

export const STRINGS = Object.freeze({
  he: Object.freeze({
    dir: 'rtl',
    switchLabel: 'שפת הצ׳אט',
    title: 'מעצב AI',
    subtitle: 'עוזר עיצוב',
    online: 'מחובר',
    onlineTitle: 'המעצב החכם מחובר.',
    comingSoon: 'בקרוב',
    comingSoonTitle: 'המעצב החכם עדיין לא מחובר.',
    placeholder: 'תאר את הארון שלך…',
    inputLabel: 'הודעה למעצב',
    send: 'שליחת הודעה',
    mic: 'דבר עם המעצב',
    micStop: 'עצור הקלטה ושלח',
    recording: 'מקליט… לחץ שוב כדי לשלוח',
    transcribing: 'ממיר דיבור לטקסט…',
    micDenied: 'אין גישה למיקרופון. אפשר גישה בדפדפן או הקלד את ההודעה.',
    voiceError: 'לא הצלחתי להבין את ההקלטה. נסה שוב.',
    readAloud: 'הקראת תשובות (קול שנוצר ב-AI)',
    readAloudOn: 'התשובות יוקראו בקול שנוצר ב-AI.',
    hint: 'Enter לשליחה · Shift+Enter לשורה חדשה',
    charCount: (n, max) => `${n.toLocaleString('he-IL')} / ${max.toLocaleString('he-IL')}`,
    pasteTruncated: (max) => `הטקסט שהודבק ארוך מ-${max.toLocaleString('he-IL')} תווים ונחתך. כדאי לקצר אותו.`,
    welcomeLabel: 'בואו נתחיל',
    welcomeTitle: 'מה נעצב היום?',
    welcomeText: 'תאר את הארון במילים שלך, ואני אהפוך את זה להצעה שתאשר לפני שמשהו משתנה.',
    suggestions: Object.freeze([
      'ארון ברוחב 240 ס"מ וגובה 260 ס"מ, לבן, עם שלושה תאים',
      'ארון גבוה עם דלתות הזזה ומוט תלייה',
      'ארבעה מדפים משמאל, תלייה באמצע ושלוש מגירות מימין',
    ]),
    conversation: 'שיחה',
    thinking: 'המעצב חושב',
    proposalHeading: 'שינויים מוצעים',
    changeCount: (n) => (n === 1 ? 'שינוי אחד' : `${n} שינויים`),
    proposalNote: 'עדיין לא הוחל. לחץ על אישור כדי להחיל את השינויים על העיצוב.',
    confirm: 'אישור',
    cancel: 'ביטול',
    notConnected: 'המעצב החכם עדיין לא מחובר. אפשר לעצב ידנית בפאנל המאפיינים.',
    stale: 'העיצוב השתנה. בקש מהמעצב הצעה חדשה.',
    agentError: 'המעצב לא הצליח לענות כרגע. נסה שוב בעוד רגע.',
    messageRejected: 'לא הצלחתי לשלוח את ההודעה הזו. אולי יש בה תווים שאינם נתמכים. נסה לנסח אותה מחדש.',
    applied: 'השינויים הוחלו. העיצוב שלך עודכן.',
    notApplied: 'לא ניתן היה להחיל את ההצעה. לא בוצע שום שינוי.',
    cancelled: 'ההצעה בוטלה. לא בוצע שום שינוי.',
    composerHints: Object.freeze({
      guided: 'ספר לי על החלל: מה הרוחב והגובה של הארון?',
      freeText: 'לדוגמה: ארון ברוחב 240 ס"מ וגובה 260 ס"מ, לבן, עם שלושה תאים',
    }),
  }),
  en: Object.freeze({
    dir: 'ltr',
    switchLabel: 'Chat language',
    title: 'AI Designer',
    subtitle: 'Design assistant',
    online: 'Online',
    onlineTitle: 'The AI designer is connected.',
    comingSoon: 'Coming soon',
    comingSoonTitle: 'The AI designer is not connected yet.',
    placeholder: 'Describe your wardrobe…',
    inputLabel: 'Message to the designer',
    send: 'Send message',
    mic: 'Talk to the designer',
    micStop: 'Stop recording and send',
    recording: 'Recording… press again to send',
    transcribing: 'Turning speech into text…',
    micDenied: 'No microphone access. Allow it in the browser, or type your message.',
    voiceError: "I couldn't understand the recording. Please try again.",
    readAloud: 'Read replies aloud (AI-generated voice)',
    readAloudOn: 'Replies will be read aloud in an AI-generated voice.',
    hint: 'Enter to send · Shift+Enter for a new line',
    charCount: (n, max) => `${n.toLocaleString('en-US')} / ${max.toLocaleString('en-US')}`,
    pasteTruncated: (max) => `The pasted text was longer than ${max.toLocaleString('en-US')} characters and was cut. Try shortening it.`,
    welcomeLabel: 'Get started',
    welcomeTitle: 'What shall we design today?',
    welcomeText: "Describe your wardrobe in your own words. I'll turn it into a proposal you confirm before anything changes.",
    suggestions: Object.freeze([
      '240 cm wide, 260 cm tall, white, three compartments',
      'Tall wardrobe with sliding doors and a hanging rail',
      'Four shelves on the left, hanging in the middle, three drawers on the right',
    ]),
    conversation: 'Conversation',
    thinking: 'The designer is thinking',
    proposalHeading: 'Proposed changes',
    changeCount: (n) => (n === 1 ? '1 change' : `${n} changes`),
    proposalNote: 'Not applied yet. Confirm to apply these changes to your design.',
    confirm: 'Confirm',
    cancel: 'Cancel',
    notConnected: "The AI designer isn't connected yet. You can design manually in the Properties panel.",
    stale: 'Design changed. Ask the designer to re-propose.',
    agentError: "The designer couldn't answer just now. Please try again in a moment.",
    messageRejected: "I couldn't send that message. It may contain unsupported characters. Please try rephrasing it.",
    applied: 'Applied. Your design has been updated.',
    notApplied: 'The proposal could not be applied. Nothing was changed.',
    cancelled: 'Proposal cancelled. No changes were made.',
    composerHints: Object.freeze({
      guided: 'Tell me about the space: how wide and tall should the wardrobe be?',
      freeText: 'e.g. 240 cm wide, 260 cm tall, white, three compartments',
    }),
  }),
});

export const stringsFor = (language) => STRINGS[language] ?? STRINGS[DEFAULT_LANGUAGE];

function readStored(storage) {
  try {
    const value = storage?.getItem(STORAGE_KEY);
    return LANGUAGES.includes(value) ? value : null;
  } catch {
    return null; // private mode / blocked storage: just use the default
  }
}

/** The chosen chat language, remembered per browser (best effort). */
export function createLanguage({ storage = globalThis.localStorage, initial } = {}) {
  let language = LANGUAGES.includes(initial) ? initial : readStored(storage) ?? DEFAULT_LANGUAGE;
  const listeners = new Set();
  return {
    get: () => language,
    strings: () => stringsFor(language),
    set(next) {
      if (!LANGUAGES.includes(next) || next === language) return;
      language = next;
      try {
        storage?.setItem(STORAGE_KEY, next);
      } catch {
        // not persisted; the choice still applies for this visit
      }
      listeners.forEach((listener) => listener(language));
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
