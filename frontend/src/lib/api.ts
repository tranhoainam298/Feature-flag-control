import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { TokenResponse } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const ACCESS_TOKEN_KEY = 'flagops_access_token';
export const REFRESH_TOKEN_KEY = 'flagops_refresh_token';

export const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Request interceptor: attach Bearer token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: auto-refresh token on 401 & format error envelope
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ code?: string; message?: string; detail?: unknown }>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If 401 and not already retried
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      // Don't loop refresh on login or refresh endpoint
      if (originalRequest.url?.includes('/auth/login') || originalRequest.url?.includes('/auth/refresh')) {
        return Promise.reject(formatApiError(error));
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (!refreshToken) {
        clearAuthTokens();
        return Promise.reject(formatApiError(error));
      }

      try {
        const refreshResponse = await axios.post<TokenResponse>(
          `${BASE_URL}/api/v1/auth/refresh`,
          { refresh_token: refreshToken }
        );
        const { access_token, refresh_token: newRefreshToken } = refreshResponse.data;
        localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
        if (newRefreshToken) {
          localStorage.setItem(REFRESH_TOKEN_KEY, newRefreshToken);
        }

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }
        processQueue(null, access_token);
        return api(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        clearAuthTokens();
        window.dispatchEvent(new Event('flagops-auth-logout'));
        return Promise.reject(formatApiError(error));
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(formatApiError(error));
  }
);

export function setAuthTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearAuthTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export interface ApiErrorFormatted {
  code: string;
  message: string;
  status: number;
}

export function formatApiError(error: AxiosError<{ code?: string; message?: string; detail?: unknown }>): ApiErrorFormatted {
  const status = error.response?.status || 500;
  const data = error.response?.data;

  let message = 'An unexpected error occurred';
  let code = 'UNKNOWN_ERROR';

  if (data?.message) {
    message = data.message;
    code = data.code || 'API_ERROR';
  } else if (typeof data?.detail === 'string') {
    message = data.detail;
  } else if (Array.isArray(data?.detail) && data.detail.length > 0) {
    message = data.detail.map((d: { msg?: string }) => d.msg || '').filter(Boolean).join(', ');
  } else if (error.message) {
    message = error.message;
  }

  return { code, message, status };
}
