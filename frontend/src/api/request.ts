import axios from "axios";
import type { ApiResponse } from "./types";

const request = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
});

request.interceptors.request.use((config) => {
  const token = localStorage.getItem("fsems_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("fsems_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default request;

export async function unwrap<T>(promise: Promise<{ data: ApiResponse<T> }>): Promise<T> {
  const { data } = await promise;
  if (!data.success) {
    throw new Error(data.message || data.error_code || "Request failed");
  }
  return data.data;
}
