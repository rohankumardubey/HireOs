"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";

import { api } from "@/lib/api";
import type { User } from "@/lib/types";

const USER_KEY = "hireos-user";
const TOKEN_KEY = "hireos-session-token";
const SESSION_EVENT = "hireos-session-change";

type SessionSnapshot = {
  user: User | null;
  token: string | null;
  hydrated: boolean;
};

const serverSnapshot: SessionSnapshot = {
  user: null,
  token: null,
  hydrated: false,
};

let lastUserRaw: string | null = null;
let lastTokenRaw: string | null = null;
let lastSnapshot: SessionSnapshot = serverSnapshot;
let bootstrapStarted = false;
let bootstrapPromise: Promise<void> | null = null;

function emitSessionChange() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(SESSION_EVENT));
  }
}

function setSnapshot(user: User | null, token: string | null, hydrated: boolean) {
  lastUserRaw = user ? JSON.stringify(user) : null;
  lastTokenRaw = token;
  lastSnapshot = { user, token, hydrated };
}

function getSnapshot(): SessionSnapshot {
  if (typeof window === "undefined") {
    return serverSnapshot;
  }

  const userRaw = localStorage.getItem(USER_KEY);
  const tokenRaw = sessionStorage.getItem(TOKEN_KEY);
  if (userRaw === lastUserRaw && tokenRaw === lastTokenRaw) {
    return lastSnapshot;
  }

  lastUserRaw = userRaw;
  lastTokenRaw = tokenRaw;
  lastSnapshot = {
    user: userRaw ? (JSON.parse(userRaw) as User) : null,
    token: tokenRaw,
    hydrated: false,
  };
  return lastSnapshot;
}

function subscribe(callback: () => void) {
  if (typeof window === "undefined") {
    return () => undefined;
  }

  const handler = () => callback();
  window.addEventListener("storage", handler);
  window.addEventListener(SESSION_EVENT, handler);

  return () => {
    window.removeEventListener("storage", handler);
    window.removeEventListener(SESSION_EVENT, handler);
  };
}

export function persistSession(user: User, token?: string | null) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  const currentToken = typeof window !== "undefined" ? sessionStorage.getItem(TOKEN_KEY) : null;
  const nextToken = token ?? currentToken;
  if (typeof window !== "undefined") {
    if (nextToken) {
      sessionStorage.setItem(TOKEN_KEY, nextToken);
    } else {
      sessionStorage.removeItem(TOKEN_KEY);
    }
  }
  setSnapshot(user, nextToken, true);
  emitSessionChange();
}

export function clearSession() {
  localStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  setSnapshot(null, null, true);
  emitSessionChange();
}

async function bootstrapSession() {
  try {
    const storedToken = typeof window !== "undefined" ? sessionStorage.getItem(TOKEN_KEY) : null;
    const user = await api.getMe(storedToken || undefined);
    persistSession(user, storedToken);
  } catch {
    clearSession();
  }
}

export function useAuth() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, () => serverSnapshot);

  useEffect(() => {
    if (snapshot.hydrated) {
      return;
    }

    if (!bootstrapStarted) {
      bootstrapStarted = true;
      bootstrapPromise = bootstrapSession().finally(() => {
        bootstrapStarted = false;
      });
      return;
    }

    void bootstrapPromise;
  }, [snapshot.hydrated]);

  return useMemo(
    () => ({
      token: snapshot.hydrated && snapshot.user ? snapshot.token || "cookie-session" : null,
      user: snapshot.user,
      loading: !snapshot.hydrated,
      isAuthenticated: Boolean(snapshot.user),
      setSession: (nextUser: User, nextToken?: string | null) => {
        persistSession(nextUser, nextToken);
      },
      logout: async () => {
        try {
          await api.logout();
        } finally {
          clearSession();
        }
      },
    }),
    [snapshot],
  );
}
