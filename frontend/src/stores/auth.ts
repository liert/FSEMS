import { defineStore } from "pinia";
import { ref } from "vue";
import { login as apiLogin } from "@/api/endpoints";

export const useAuthStore = defineStore("auth", () => {
  const token = ref(localStorage.getItem("fsems_token") || "");
  const username = ref(localStorage.getItem("fsems_username") || "");

  function setToken(value: string) {
    token.value = value;
    localStorage.setItem("fsems_token", value);
  }

  function setUsername(value: string) {
    username.value = value;
    localStorage.setItem("fsems_username", value);
  }

  function logout() {
    token.value = "";
    username.value = "";
    localStorage.removeItem("fsems_token");
    localStorage.removeItem("fsems_username");
  }

  async function login(user: string, password: string) {
    const data = await apiLogin(user, password);
    setToken(data.access_token);
    setUsername(user);
  }

  const isLoggedIn = () => !!token.value;

  return { token, username, setToken, setUsername, logout, login, isLoggedIn };
});
