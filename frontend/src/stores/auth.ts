import { defineStore } from "pinia";
import { ref } from "vue";
import { login as apiLogin } from "@/api/endpoints";

export const useAuthStore = defineStore("auth", () => {
  const token = ref(localStorage.getItem("fsems_token") || "");

  function setToken(value: string) {
    token.value = value;
    localStorage.setItem("fsems_token", value);
  }

  function logout() {
    token.value = "";
    localStorage.removeItem("fsems_token");
  }

  async function login(username: string, password: string) {
    const data = await apiLogin(username, password);
    setToken(data.access_token);
  }

  const isLoggedIn = () => !!token.value;

  return { token, setToken, logout, login, isLoggedIn };
});
