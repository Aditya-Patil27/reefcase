import createClient from "openapi-fetch";
import { config } from "../config";
import type { paths } from "./schema";

/** Typed client generated from src/api/schema.d.ts. Every path is a literal in `paths`. */
export const api = createClient<paths>({ baseUrl: config.API_URL });
