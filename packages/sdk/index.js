export class KouroshError extends Error {
  constructor(error) {
    const normalized = error && typeof error === "object"
      ? error
      : { code: "unknown_error", message: "bridge call failed" };
    super(typeof normalized.message === "string" ? normalized.message : "bridge call failed");
    this.name = "KouroshError";
    this.code = typeof normalized.code === "string" ? normalized.code : "unknown_error";
  }
}

export async function invoke(method, args, options) {
  if (!globalThis.kourosh || typeof globalThis.kourosh.invoke !== "function") {
    throw new KouroshError({
      code: "bridge_unavailable",
      message: "the Kourosh bridge has not been initialized",
    });
  }
  try {
    return await globalThis.kourosh.invoke(method, args, options);
  } catch (error) {
    throw new KouroshError(error);
  }
}
