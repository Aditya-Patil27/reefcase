import createClient from "openapi-fetch";
import { config } from "../config";
import type { paths } from "./schema";

/** Typed client generated from src/api/schema.d.ts. Every path is a literal in `paths`. */
export const api = createClient<paths>({ baseUrl: config.API_URL });

/**
 * openapi-fetch returns a failed response instead of throwing, so a query would read a 500 as
 * an empty record. This throws it into the query's error state. A 404 means "not there" and
 * stays null.
 */
export function dataOrNull<T>(result: { data?: T; response: Response }): T | null {
  if (result.data !== undefined) return result.data;
  if (result.response.status === 404) return null;
  throw new Error(`${result.response.status} ${result.response.statusText}`.trim());
}
