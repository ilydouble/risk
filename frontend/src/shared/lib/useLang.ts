import { useTranslation } from "react-i18next";

/**
 * useLang — 语言与本地化取值的小工具。
 *
 * 站内数据（企业名、案例标题等）多为中英双语字段，
 * 用 pick() 按当前语言取值，避免在各组件里重复判断。
 */
export function useLang() {
  const { i18n } = useTranslation();
  const isEn = (i18n.resolvedLanguage ?? "zh").startsWith("en");
  const pick = (zh?: string, en?: string): string =>
    isEn && en ? en : (zh ?? "");

  return { isEn, lang: isEn ? ("en" as const) : ("zh" as const), pick };
}
