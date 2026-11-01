import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const CrumbContext = createContext<{
  crumb: string | null;
  setCrumb: (crumb: string | null) => void;
}>({
  crumb: null,
  setCrumb: () => {},
});

export function CrumbProvider({ children }: { children: ReactNode }) {
  const [crumb, setCrumb] = useState<string | null>(null);
  return (
    <CrumbContext.Provider value={{ crumb, setCrumb }}>
      {children}
    </CrumbContext.Provider>
  );
}

export function useCrumb(initialCrumb?: string | null) {
  const context = useContext(CrumbContext);
  const { setCrumb } = context;
  useEffect(() => {
    if (initialCrumb !== undefined) {
      setCrumb(initialCrumb);
      return () => setCrumb(null);
    }
  }, [initialCrumb, setCrumb]);
  return context;
}
