# Handling JavaScript-to-Python RPC

The bridge request envelope is:

```json
{
  "protocol": 1,
  "id": "js-mabc-1",
  "method": "greet",
  "args": {"name": "Akira"}
}
```

The Python side registers `greet`; Rust validates the origin, protocol,
request ID, method, arguments, size, queue capacity, and deadline before
dispatch. Responses contain the same request ID and either `ok: true` with a
result or `ok: false` with a structured error.

```ts
try {
  const result = await invoke<{ message: string }>("greet", { name: "Akira" });
} catch (error) {
  // KouroshError exposes code, message, requestId, and safe details.
}
```

Unknown methods, invalid arguments, unsupported protocol versions, untrusted
origins, oversized requests, timeouts, transport failures, and shutdowns are
rejected. Do not widen the registry or origin policy to make a call work.

The browser helper never evaluates response text and exposes no shell,
filesystem, import, or arbitrary-evaluation method. See the [protocol
reference](../api/protocol.md) and [threat model](../architecture/threat-model.md).
