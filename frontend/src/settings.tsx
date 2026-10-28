// Role and actor name, kept on this device (there is no login).
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { lsGet, lsSet } from "./util";

export type Role = "facilitator" | "assessor" | "admin" | "rater";
export const ROLES: Role[] = ["facilitator", "assessor", "admin", "rater"];

interface Settings {
  role: Role | null;
  actor: string;
  setRole: (r: Role) => void;
  setActor: (a: string) => void;
}

const Ctx = createContext<Settings | null>(null);

function readRole(): Role | null {
  const r = lsGet("hunar.role");
  return ROLES.includes(r as Role) ? (r as Role) : null;
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role | null>(readRole);
  const [actor, setActorState] = useState<string>(() => lsGet("hunar.actor") ?? "");
  const setRole = useCallback((r: Role) => {
    setRoleState(r);
    lsSet("hunar.role", r);
  }, []);
  const setActor = useCallback((a: string) => {
    setActorState(a);
    lsSet("hunar.actor", a);
  }, []);
  const value = useMemo(() => ({ role, actor, setRole, setActor }), [role, actor, setRole, setActor]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSettings(): Settings {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSettings outside SettingsProvider");
  return v;
}

/** The name written to the audit log; falls back to the role when no name was entered. */
export function actorName(s: Settings): string {
  return s.actor.trim() || s.role || "facilitator";
}
