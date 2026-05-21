/** useExport — wraps an export call with loading state + toast feedback. */
import { useState } from "react";

import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

export function useExport() {
  const accessToken = useAuthStore(s => s.accessToken);
  const [exporting, setExporting] = useState(false);

  const run = async (fn: (token: string | null) => Promise<void>, what: string) => {
    setExporting(true);
    try {
      await fn(accessToken);
      toast.success(`${what} descarregat`);
    } catch (err) {
      toast.error((err as Error).message || `No s'ha pogut exportar ${what}`);
    } finally {
      setExporting(false);
    }
  };

  return { exporting, run };
}
