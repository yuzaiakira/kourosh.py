const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const bridgeSource = fs.readFileSync(
  path.join(__dirname, "..", "examples", "hello-vanilla", "bridge.js"),
  "utf8",
);

function createBridge(postMessage) {
  const window = { ipc: { postMessage } };
  const context = {
    window,
    TextEncoder,
    Promise,
    setTimeout,
    clearTimeout,
    Date,
  };
  vm.runInNewContext(bridgeSource, context);
  return window;
}

test("resolves a successful response by request ID", async () => {
  let rawRequest;
  const window = createBridge((raw) => { rawRequest = JSON.parse(raw); });
  const promise = window.kourosh.invoke("greet", { name: "Ada" });
  window.__kouroshReceive({
    id: rawRequest.id,
    ok: true,
    result: { message: "Hello, Ada!" },
  });
  assert.deepEqual(await promise, { message: "Hello, Ada!" });
});

test("rejects structured Python and unknown-method errors", async () => {
  let rawRequest;
  const window = createBridge((raw) => { rawRequest = JSON.parse(raw); });
  const promise = window.kourosh.invoke("unknown", {});
  window.__kouroshReceive({
    id: rawRequest.id,
    ok: false,
    error: { code: "method_not_allowed", message: "not allowlisted" },
  });
  await assert.rejects(promise, (error) => error.code === "method_not_allowed");
});

test("cleans up pending calls on transport failure, close, and timeout", async () => {
  const transportWindow = createBridge(() => { throw new Error("closed"); });
  await assert.rejects(
    transportWindow.kourosh.invoke("greet", { name: "Ada" }),
    (error) => error.code === "transport_error",
  );

  let closeRequest;
  const closeWindow = createBridge((raw) => { closeRequest = JSON.parse(raw); });
  const pending = closeWindow.kourosh.invoke("greet", { name: "Ada" });
  closeWindow.__kouroshRejectAll();
  await assert.rejects(pending, (error) => error.code === "window_closed");
  assert.equal(closeRequest.method, "greet");

  const timeoutWindow = createBridge(() => {});
  await assert.rejects(
    timeoutWindow.kourosh.invoke("greet", { name: "Ada" }, { timeoutMs: 1 }),
    (error) => error.code === "timeout",
  );
});
