import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const STORAGE_KEY = "credit-demo-mode";

interface DemoModeValue {
  demoMode: boolean;
  initialized: boolean;
  initialize: () => void;
  toggleDemoMode: () => void;
}

const DemoModeContext = createContext<DemoModeValue | undefined>(undefined);

export function DemoModeProvider({ children }: { children: ReactNode }) {
  const [demoMode, setDemoMode] = useState(false);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) === "1") {
        setDemoMode(true);
        setInitialized(true);
      }
    } catch {
      /* storage unavailable, fall back to in-memory state */
    }
  }, []);

  const initialize = useCallback(() => {
    setDemoMode(true);
    setInitialized(true);
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
  }, []);

  const toggleDemoMode = useCallback(() => {
    setDemoMode((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({ demoMode, initialized, initialize, toggleDemoMode }),
    [demoMode, initialized, initialize, toggleDemoMode],
  );

  return <DemoModeContext.Provider value={value}>{children}</DemoModeContext.Provider>;
}

export function useDemoMode(): DemoModeValue {
  const ctx = useContext(DemoModeContext);
  if (!ctx) {
    throw new Error("useDemoMode must be used within DemoModeProvider");
  }
  return ctx;
}