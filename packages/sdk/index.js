const METHOD_PATTERN = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;

export function normalizeError(error, fallback = "bridge call failed") {
  if (!error || typeof error !== "object") {
    return { code: "unknown_error", message: fallback };
  }
  const normalized = {
    code: typeof error.code === "string" && error.code ? error.code : "unknown_error",
    message: typeof error.message === "string" && error.message ? error.message : fallback,
  };
  if (typeof error.requestId === "string") normalized.requestId = error.requestId;
  if (Object.hasOwn(error, "details")) normalized.details = error.details;
  return normalized;
}

export class KouroshError extends Error {
  constructor(error) {
    const normalized = normalizeError(error);
    super(normalized.message);
    this.name = "KouroshError";
    this.code = normalized.code;
    if (normalized.requestId !== undefined) this.requestId = normalized.requestId;
    if (normalized.details !== undefined) this.details = normalized.details;
  }
}

function invalidArgument(code, message) {
  throw new KouroshError({ code, message });
}

function assertJsonValue(_key, value) {
  if (typeof value === "undefined" || typeof value === "function" || typeof value === "symbol" || typeof value === "bigint") {
    throw new TypeError("value is not JSON serializable");
  }
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new TypeError("number must be finite");
  }
  return value;
}

export async function invoke(method, args, options) {
  if (typeof method !== "string" || !METHOD_PATTERN.test(method)) {
    invalidArgument("invalid_method", "method must match [A-Za-z_][A-Za-z0-9_]{0,63}");
  }
  if (!args || typeof args !== "object" || Array.isArray(args)) {
    invalidArgument("invalid_args", "args must be a JSON object");
  }
  try {
    JSON.stringify(args, assertJsonValue);
  } catch (_error) {
    invalidArgument("invalid_args", "args must be JSON serializable");
  }
  if (options !== undefined && (!options || typeof options !== "object" || Array.isArray(options))) {
    invalidArgument("invalid_options", "options must be an object");
  }
  if (!globalThis.kourosh || typeof globalThis.kourosh.invoke !== "function") {
    throw new KouroshError({
      code: "bridge_unavailable",
      message: "the Kourosh bridge has not been initialized",
    });
  }
  try {
    return await globalThis.kourosh.invoke(method, args, options);
  } catch (error) {
    if (error instanceof KouroshError) throw error;
    throw new KouroshError(error);
  }
}
