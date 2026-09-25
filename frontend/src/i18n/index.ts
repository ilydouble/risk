import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import messages from './local/index';

export const SUPPORTED_LANGUAGES = ['zh', 'en'] as const;
export type AppLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const LANGUAGE_STORAGE_KEY = 'credit-lang';

/** 读取上次选择的语言；默认中文（与站内内容语言一致）。 */
export function getInitialLanguage(): AppLanguage {
  try {
    const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (stored === 'en' || stored === 'zh') return stored;
  } catch {
    /* storage unavailable, fall through to default */
  }
  return 'zh';
}

i18n.use(initReactI18next).init({
  lng: getInitialLanguage(),
  fallbackLng: 'zh',
  supportedLngs: SUPPORTED_LANGUAGES,
  resources: messages,
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;