import axios, { AxiosHeaders } from "axios";
import type { AxiosError } from "axios";

import { clearStoredSession, getStoredSession } from "../utils/auth";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const apiClient = axios.create({
  baseURL
});

apiClient.interceptors.request.use((config) => {
  const session = getStoredSession();
  if (session?.token) {
    const headers = new AxiosHeaders(config.headers);
    headers.set("Authorization", `Bearer ${session.token}`);
    config.headers = headers;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error?.response?.status === 401) {
      const requestUrl = error?.config?.url ?? "";
      if (requestUrl.endsWith("/auth/login") || requestUrl.endsWith("/auth/setup")) {
        return Promise.reject(error);
      }
      clearStoredSession();
      window.location.reload();
    }
    return Promise.reject(error);
  }
);
