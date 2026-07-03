export type ThemeMode = "dark" | "light";

const THEME_KEY = "fsems_theme";
const SIDEBAR_KEY = "fsems_sidebar_collapsed";

export function getStoredTheme(): ThemeMode {
  return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
}

export function applyThemeClass(mode: ThemeMode) {
  document.documentElement.classList.toggle("dark", mode === "dark");
  document.documentElement.classList.toggle("light", mode === "light");
}

export function getStoredSidebarCollapsed(): boolean {
  return localStorage.getItem(SIDEBAR_KEY) === "1";
}

export function persistSidebarCollapsed(collapsed: boolean) {
  localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
}

export function persistTheme(mode: ThemeMode) {
  localStorage.setItem(THEME_KEY, mode);
}
