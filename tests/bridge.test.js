const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const bridgeSource = fs.readFileSync(
  path.join(__dirname, "..", "examples", "hello-vanilla", "bridge.js"),
  "utf8",
);
const sdkSource = fs.readFileSync(
  path.join(__dirname, "..", "packages", "sdk", "kourosh.js"),
  "utf8",
);

function createBridge(postMessage, source = bridgeSource) {
  const listeners = new Map();
  const window = {
    ipc: { postMessage },
    addEventListener(name, callback) { listeners.set(name, callback); },
    __listeners: listeners,
  };
  const context = {
    window,
    TextEncoder,
    Promise,
    setTimeout,
    clearTimeout,
    Date,
  };
  vm.runInNewContext(source, context);
  return window;
}

test("resolves a successful response by request ID", async () => {
  let rawRequest;
  const window = createBridge((raw) => { rawRequest = JSON.parse(raw); });
  const promise = window.kourosh.invoke("greet", { name: "Ada" });
  assert.equal(rawRequest.protocol, 1);
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

test("rejects invalid methods, arguments, options, and malformed responses", async () => {
  const window = createBridge(() => {});
  await assert.rejects(window.kourosh.invoke("read-file", {}), (error) => error.code === "invalid_method");
  await assert.rejects(window.kourosh.invoke("greet", []), (error) => error.code === "invalid_args");
  await assert.rejects(window.kourosh.invoke("greet", { value: undefined }), (error) => error.code === "invalid_args");
  await assert.rejects(window.kourosh.invoke("greet", { value: Number.NaN }), (error) => error.code === "invalid_args");
  await assert.rejects(window.kourosh.invoke("greet", {}, null), (error) => error.code === "invalid_options");

  let request;
  const responseWindow = createBridge((raw) => { request = JSON.parse(raw); });
  const pending = responseWindow.kourosh.invoke("greet", {});
  responseWindow.__kouroshReceive({ id: request.id, ok: "yes" });
  await assert.rejects(pending, (error) => error.code === "malformed_response");
});

test("ships the same framework-independent SDK contract", async () => {
  let rawRequest;
  const window = createBridge((raw) => { rawRequest = JSON.parse(raw); }, sdkSource);
  const promise = window.kourosh.invoke("greet", { name: "SDK" });
  window.__kouroshReceive({ id: rawRequest.id, ok: true, result: { message: "Hello, SDK!" } });
  assert.deepEqual(await promise, { message: "Hello, SDK!" });
});

test("maps structured bridge failures through the official module SDK", async () => {
  const { invoke, KouroshError, PROTOCOL_VERSION } = await import("../packages/sdk/index.js");
  assert.equal(PROTOCOL_VERSION, 1);
  const previous = globalThis.kourosh;
  globalThis.kourosh = { invoke: async () => { throw { code: "method_not_allowed", message: "denied", requestId: "rpc-1" }; } };
  await assert.rejects(invoke("secret", {}), (error) => {
    assert.ok(error instanceof KouroshError);
    return error.code === "method_not_allowed" && error.message === "denied" && error.requestId === "rpc-1";
  });
  globalThis.kourosh = previous;
});

test("validates the framework-independent SDK before using the bridge", async () => {
  const { invoke } = await import("../packages/sdk/index.js");
  const previous = globalThis.kourosh;
  globalThis.kourosh = { invoke: async () => ({ ok: true }) };
  await assert.rejects(invoke("bad-name", {}), (error) => error.code === "invalid_method");
  await assert.rejects(invoke("greet", []), (error) => error.code === "invalid_args");
  await assert.rejects(invoke("greet", { value: BigInt(1) }), (error) => error.code === "invalid_args");
  globalThis.kourosh = previous;
});

test("rejects pending calls when the renderer reloads", async () => {
  const window = createBridge(() => {});
  const pending = window.kourosh.invoke("greet", { name: "reload" });
  window.__listeners.get("beforeunload")();
  await assert.rejects(pending, (error) => error.code === "window_reloaded");
});

test("matches concurrent responses by request ID", async () => {
  const requests = [];
  const window = createBridge((raw) => requests.push(JSON.parse(raw)));
  const promises = Array.from({ length: 16 }, (_value, index) => window.kourosh.invoke("greet", { name: String(index) }));
  assert.equal(requests.length, 16);
  for (const request of [...requests].reverse()) {
    window.__kouroshReceive({ id: request.id, ok: true, result: { index: request.args.name } });
  }
  const results = await Promise.all(promises);
  assert.deepEqual(results.map((result) => result.index), Array.from({ length: 16 }, (_value, index) => String(index)));
});
