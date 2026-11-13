import { useCallback, useState, useSyncExternalStore } from "react";

function subscribeOnline(callback: () => void): () => void {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

/** True while the browser reports a network connection. */
export function useOnline(): boolean {
  return useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
}

export type LocateStatus = "idle" | "locating" | "denied" | "unavailable" | "failed";

/**
 * Ask the browser for the user's position once, on request.
 * The position is only handed to the caller; it is never stored or sent anywhere by this hook.
 */
export function useGeolocation() {
  const [status, setStatus] = useState<LocateStatus>("idle");

  const locate = useCallback((onPosition: (lat: number, lon: number) => void) => {
    if (!("geolocation" in navigator)) {
      setStatus("unavailable");
      return;
    }
    setStatus("locating");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setStatus("idle");
        onPosition(position.coords.latitude, position.coords.longitude);
      },
      (error) => setStatus(error.code === error.PERMISSION_DENIED ? "denied" : "failed"),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    );
  }, []);

  return { status, locate };
}
