/**
 * App-wide i18n: one vue-i18n instance, messages from `src/locales/`.
 *
 * The active locale mirrors `uiStore.settings.locale` (persisted in the
 * same `webui:settings` blob as the theme); the store syncs it via a
 * `watchEffect`. `i18n.global.t` is safe outside component setup — use it
 * in stores and composables.
 */

import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import zh from './locales/zh.json'

export type Locale = 'en' | 'zh'

export const LOCALE_NAMES: Record<Locale, string> = { en: 'English', zh: '中文' }

/** Mirrors SETTINGS_KEY in stores/ui.ts (duplicated to avoid a circular import). */
const SETTINGS_KEY = 'webui:settings'

function initialLocale(): Locale {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    const parsed = raw ? (JSON.parse(raw) as { locale?: string }) : null
    if (parsed?.locale === 'zh' || parsed?.locale === 'en') return parsed.locale
  } catch {
    /* unavailable or corrupted -> fall through to browser detection */
  }
  return navigator.language?.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: 'en',
  messages: { en, zh },
  missingWarn: false,
  fallbackWarn: false,
})

export function setLocale(locale: Locale) {
  i18n.global.locale.value = locale
}
