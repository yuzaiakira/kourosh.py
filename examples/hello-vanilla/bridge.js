(() => {
  "use strict";
  if (window.__kouroshInstalled) return;
  window.__kouroshInstalled = true;
  const MAX_REQUEST_BYTES = 64 * 1024;
  const MAX_PENDING_REQUESTS = 32;
  const DEFAULT_TIMEOUT_MS = 5000;
  const pending = new Map();
  let sequence = 0;

  function nextId() {
    sequence += 1;
    return `js-${Date.now().toString(36)}-${sequence.toString(36)}`;
  }

  window.__kouroshReceive = (response) => {
    if (!response || typeof response.id !== "string") return;
    const call = pending.get(response.id);
    if (!call) return;
    pending.delete(response.id);
    clearTimeout(call.timer);
    if (response.ok === true) call.resolve(response.result);
    else call.reject(response.error || { code: "unknown_error", message: "bridge call failed" });
  };

  window.__kouroshRejectAll = (error = { code: "window_closed", message: "window is closing" }) => {
    for (const call of pending.values()) {
      clearTimeout(call.timer);
      call.reject(error);
    }
    pending.clear();
  };
  window.addEventListener?.("beforeunload", () => window.__kouroshRejectAll({
    code: "window_reloaded",
    message: "the renderer is reloading",
  }));

  window.kourosh = Object.freeze({
    invoke(method, args, options = {}) {
      if (typeof method !== "string" || !method) {
        return Promise.reject({ code: "invalid_method", message: "method must be a non-empty string" });
      }
      const id = nextId();
      const raw = JSON.stringify({ id, method, args });
      if (new TextEncoder().encode(raw).byteLength > MAX_REQUEST_BYTES) {
        return Promise.reject({ code: "request_too_large", message: "request exceeds the bridge limit" });
      }
      if (!window.ipc || typeof window.ipc.postMessage !== "function") {
        return Promise.reject({ code: "bridge_unavailable", message: "the native host IPC channel is unavailable" });
      }
      if (pending.size >= MAX_PENDING_REQUESTS) {
        return Promise.reject({ code: "busy", message: "too many bridge calls are in flight" });
      }
      const timeoutMs = Number.isFinite(options.timeoutMs) && options.timeoutMs > 0
        ? Math.min(options.timeoutMs, DEFAULT_TIMEOUT_MS)
        : DEFAULT_TIMEOUT_MS;
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pending.delete(id);
          reject({ code: "timeout", message: "the bridge call timed out" });
        }, timeoutMs);
        pending.set(id, { resolve, reject, timer });
        try {
          window.ipc.postMessage(raw);
        } catch (_error) {
          pending.delete(id);
          clearTimeout(timer);
          reject({ code: "transport_error", message: "the native IPC channel rejected the request" });
        }
      });
    },
  });
})();
