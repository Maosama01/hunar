// The logged-in account and its bearer token, kept in localStorage so staff can keep working offline
// after a reload. Not React: the API client reads the token for every request, including sync replay.
import { useSyncExternalStore } from "react";
import type { Account, AccountRole } from "./api";
import { lsGet, lsRemove, lsSet } from "./util";

const TOKEN_KEY = "hunar.token";
const ACCOUNT_KEY = "hunar.account";

export const STAFF_ROLES: AccountRole[] = ["facilitator", "assessor", "admin"];

export type EndReason = "logout" | "expired" | "erased";

export interface SessionState {
  token: string | null;
  account: Account | null;
  /** Why the last session ended (shown once on the login or welcome screen). */
  ended: EndReason | null;
  /** Where the route guards send the person after the session ended (default: the login screen). */
  next: string | null;
}

function readAccount(): Account | null {
  try {
    const raw = lsGet(ACCOUNT_KEY);
    return raw ? (JSON.parse(raw) as Account) : null;
  } catch {
    return null;
  }
}

let state: SessionState = (() => {
  const token = lsGet(TOKEN_KEY);
  const account = token ? readAccount() : null;
  return { token: token && account ? token : null, account: token ? account : null, ended: null, next: null };
})();
const listeners = new Set<() => void>();

function emit(next: SessionState) {
  state = next;
  listeners.forEach((l) => l());
}

export function getSession(): SessionState {
  return state;
}

export function getToken(): string | null {
  return state.token;
}

export function isStaff(acc: Account | null | undefined = state.account): boolean {
  return !!acc && STAFF_ROLES.includes(acc.role);
}

export function setSession(token: string, account: Account): void {
  lsSet(TOKEN_KEY, token);
  lsSet(ACCOUNT_KEY, JSON.stringify(account));
  emit({ token, account, ended: null, next: null });
}

export function updateAccount(account: Account): void {
  if (!state.token) return;
  lsSet(ACCOUNT_KEY, JSON.stringify(account));
  emit({ ...state, account });
}

/** End the session on this device. Queued offline changes (Dexie outbox) are NOT touched: they are
 * sent by the next staff login. */
export function clearSession(reason: EndReason, next: string | null = null): void {
  lsRemove(TOKEN_KEY);
  lsRemove(ACCOUNT_KEY);
  emit({ token: null, account: null, ended: reason, next });
}

export function acknowledgeEnded(): void {
  if (state.ended || state.next) emit({ ...state, ended: null, next: null });
}

export function subscribeSession(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useSession(): SessionState {
  return useSyncExternalStore(subscribeSession, getSession, getSession);
}

/** Where each role starts. */
export function homePath(acc: Account | null | undefined): string {
  if (!acc) return "/welcome";
  if (acc.role === "worker") return "/w/quiz";
  if (acc.role === "customer") return "/c/find";
  return "/staff";
}
