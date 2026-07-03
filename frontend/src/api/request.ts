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

function extractApiErrorMessage(error: unknown): string | undefined {
  if (!error || typeof error !== "object" || !("response" in error)) {
    return undefined;
  }
  const data = (error as { response?: { data?: unknown } }).response?.data;
  if (!data || typeof data !== "object") {
    return undefined;
  }
  const payload = data as { message?: string; detail?: unknown };
  if (payload.message) {
    return payload.message;
  }
  const detail = payload.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: string }).message;
    return message || undefined;
  }
  return undefined;
}

request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("fsems_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    const apiMessage = extractApiErrorMessage(error);
    if (apiMessage) {
      error.message = apiMessage;
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
