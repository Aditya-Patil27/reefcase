import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

/** Runs every §6.3 path from the fixtures when VITE_MOCK_API=1. */
export const worker = setupWorker(...handlers);
