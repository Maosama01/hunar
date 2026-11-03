// Role and display name of the logged-in staff account. (Before accounts existed these were picked on
// the device; the server now ignores names in request bodies and records the logged-in account.)
import type { AccountRole } from "./api";
import { useSession } from "./session";

export type Role = AccountRole;

interface Settings {
  role: Role | null;
  /** Display name of the logged-in account (shown in the UI; the audit log uses the account id). */
  actor: string;
}

export function useSettings(): Settings {
  const { account } = useSession();
  return { role: account?.role ?? null, actor: account?.display_name ?? "" };
}

/** The name shown next to queued changes; the server records the logged-in account as the actor. */
export function actorName(s: Settings): string {
  return s.actor.trim() || s.role || "staff";
}
