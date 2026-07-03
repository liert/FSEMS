import { defineStore } from "pinia";
import { ref } from "vue";
import {
  applyThemeClass,
  getStoredSidebarCollapsed,
  getStoredTheme,
  persistSidebarCollapsed,
  persistTheme,
  type ThemeMode,
} from "@/utils/theme";

export const useUiStore = defineStore("ui", () => {
  const sidebarCollapsed = ref(getStoredSidebarCollapsed());
  const theme = ref<ThemeMode>(getStoredTheme());
  const pageBreadcrumbLabel = ref<string | null>(null);

  function applyTheme() {
    applyThemeClass(theme.value);
    persistTheme(theme.value);
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value;
    persistSidebarCollapsed(sidebarCollapsed.value);
  }

  function setTheme(mode: ThemeMode) {
    theme.value = mode;
    applyTheme();
  }

  function toggleTheme() {
    setTheme(theme.value === "dark" ? "light" : "dark");
  }

  function setPageBreadcrumbLabel(label: string | null) {
    pageBreadcrumbLabel.value = label;
  }

  applyTheme();

  return {
    sidebarCollapsed,
    theme,
    pageBreadcrumbLabel,
    toggleSidebar,
    setTheme,
    toggleTheme,
    setPageBreadcrumbLabel,
  };
});
