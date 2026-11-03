// /api/trades (trade names, qualification and bookable jobs), fetched once per app session.
import { useEffect, useState } from "react";
import { api, type TradesOut } from "./api";

let cache: TradesOut | null = null;
let pending: Promise<TradesOut> | null = null;

export function loadTrades(): Promise<TradesOut> {
  if (cache) return Promise.resolve(cache);
  pending ??= api.trades().then((t) => (cache = t)).finally(() => (pending = null));
  return pending;
}

export function useTrades(): { trades: TradesOut | null; error: unknown } {
  const [trades, setTrades] = useState<TradesOut | null>(cache);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (cache) return;
    let alive = true;
    loadTrades()
      .then((t) => alive && setTrades(t))
      .catch((e) => alive && setError(e));
    return () => {
      alive = false;
    };
  }, []);
  return { trades, error };
}
