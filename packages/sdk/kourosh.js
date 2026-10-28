(() => {
  "use strict";
  if (window.__kouroshInstalled) return;
  window.__kouroshInstalled = true;
  const PROTOCOL_VERSION = 1;
  const MAX_REQUEST_BYTES = 64 * 1024;
  const MAX_PENDING_REQUESTS = 32;
  const DEFAULT_TIMEOUT_MS = 5000;
  const METHOD_PATTERN = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;
  const pending = new Map();
  let sequence = 0;

  function nextId() {
    sequence += 1;
    return `js-${Date.now().toString(36)}-${sequence.toString(36)}`;
  }

  function normalizeError(error, fallback = "bridge call failed") {
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

  window.__kouroshReceive = (response) => {
    if (!response || typeof response.id !== "string") return;
    const call = pending.get(response.id);
    if (!call) return;
    pending.delete(response.id);
    clearTimeout(call.timer);
    if (response.ok === true) {
      call.resolve(response.result);
    } else if (response.ok === false) {
      call.reject(normalizeError(response.error));
    } else {
      call.reject({ code: "malformed_response", message: "the native host returned an invalid response" });
    }
  };

  window.__kouroshRejectAll = (error = { code: "window_closed", message: "window is closing" }) => {
    const normalized = normalizeError(error, "window is closing");
    for (const call of pending.values()) {
      clearTimeout(call.timer);
      call.reject(normalized);
    }
    pending.clear();
  };
  window.addEventListener?.("beforeunload", () => window.__kouroshRejectAll({
    code: "window_reloaded",
    message: "the renderer is reloading",
  }));

  window.kourosh = Object.freeze({
    invoke(method, args, options = {}) {
      if (typeof method !== "string" || !METHOD_PATTERN.test(method)) {
        return Promise.reject({ code: "invalid_method", message: "method must match [A-Za-z_][A-Za-z0-9_]{0,63}" });
      }
      if (!args || typeof args !== "object" || Array.isArray(args)) {
        return Promise.reject({ code: "invalid_args", message: "args must be a JSON object" });
      }
      if (!options || typeof options !== "object" || Array.isArray(options)) {
        return Promise.reject({ code: "invalid_options", message: "options must be an object" });
      }
      if (pending.size >= MAX_PENDING_REQUESTS) {
        return Promise.reject({ code: "busy", message: "too many bridge calls are in flight" });
      }
      const id = nextId();
      let raw;
      try {
        raw = JSON.stringify({ protocol: PROTOCOL_VERSION, id, method, args });
      } catch (_error) {
        return Promise.reject({ code: "invalid_args", message: "args must be JSON serializable" });
      }
      if (typeof raw !== "string" || new TextEncoder().encode(raw).byteLength > MAX_REQUEST_BYTES) {
        return Promise.reject({ code: "request_too_large", message: "request exceeds the bridge limit" });
      }
      if (!window.ipc || typeof window.ipc.postMessage !== "function") {
        return Promise.reject({ code: "bridge_unavailable", message: "the native host IPC channel is unavailable" });
      }
      const timeoutMs = Number.isFinite(options.timeoutMs) && options.timeoutMs > 0
        ? Math.min(Math.max(options.timeoutMs, 1), DEFAULT_TIMEOUT_MS)
        : DEFAULT_TIMEOUT_MS;
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pending.delete(id);
          reject({ code: "timeout", message: "the bridge call timed out", requestId: id });
        }, timeoutMs);
        pending.set(id, { resolve, reject, timer });
        try {
          window.ipc.postMessage(raw);
        } catch (_error) {
          pending.delete(id);
          clearTimeout(timer);
          reject({ code: "transport_error", message: "the native IPC channel rejected the request", requestId: id });
        }
      });
    },
  });
})();
