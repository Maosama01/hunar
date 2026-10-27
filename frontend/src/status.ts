// Connectivity and sync status, shared by the API client, the sync engine and the header.
import { useSyncExternalStore } from "react";

export interface SyncStatus {
  /** navigator.onLine */
  online: boolean;
  /** Whether the last request reached the API (null = not tried yet). */
  reachable: boolean | null;
  syncing: boolean;
  lastSyncAt: string | null;
  lastError: string | null;
}

let state: SyncStatus = {
  online: typeof navigator === "undefined" ? true : navigator.onLine,
  reachable: null,
  syncing: false,
  lastSyncAt: null,
  lastError: null,
};
const listeners = new Set<() => void>();

export function getStatus(): SyncStatus {
  return state;
}

export function setStatus(patch: Partial<SyncStatus>): void {
  let changed = false;
  for (const k of Object.keys(patch) as (keyof SyncStatus)[]) {
    if (state[k] !== patch[k]) changed = true;
  }
  if (!changed) return;
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

export function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useStatus(): SyncStatus {
  return useSyncExternalStore(subscribe, getStatus, getStatus);
}

/** True when we believe the API can be reached right now. */
export function isConnected(s: SyncStatus = state): boolean {
  return s.online && s.reachable !== false;
}
