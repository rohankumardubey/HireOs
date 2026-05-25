"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";

import { api } from "@/lib/api";
import type { User } from "@/lib/types";

const USER_KEY = "hireos-user";
const SESSION_EVENT = "hireos-session-change";

type SessionSnapshot = {
  user: User | null;
  hydrated: boolean;
};

const serverSnapshot: SessionSnapshot = {
  user: null,
  hydrated: false,
};

let lastUserRaw: string | null = null;
let lastSnapshot: SessionSnapshot = serverSnapshot;
let bootstrapStarted = false;
let bootstrapPromise: Promise<void> | null = null;

function emitSessionChange() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(SESSION_EVENT));
  }
}

function setSnapshot(user: User | null, hydrated: boolean) {
  lastUserRaw = user ? JSON.stringify(user) : null;
  lastSnapshot = { user, hydrated };
}

function getSnapshot(): SessionSnapshot {
  if (typeof window === "undefined") {
    return serverSnapshot;
  }

  const userRaw = localStorage.getItem(USER_KEY);
  if (userRaw === lastUserRaw && lastSnapshot.hydrated) {
    return lastSnapshot;
  }

  lastUserRaw = userRaw;
  lastSnapshot = {
    user: userRaw ? (JSON.parse(userRaw) as User) : null,
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

export function persistSession(user: User) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  setSnapshot(user, true);
  emitSessionChange();
}

export function clearSession() {
  localStorage.removeItem(USER_KEY);
  setSnapshot(null, true);
  emitSessionChange();
}

async function bootstrapSession() {
  try {
    const user = await api.getMe();
    persistSession(user);
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
      token: snapshot.hydrated && snapshot.user ? "cookie-session" : null,
      user: snapshot.user,
      loading: !snapshot.hydrated,
      isAuthenticated: Boolean(snapshot.user),
      setSession: (nextUser: User) => {
        persistSession(nextUser);
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
