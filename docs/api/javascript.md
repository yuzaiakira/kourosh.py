# JavaScript and TypeScript SDK reference

Generated React projects include a local `@kourosh/sdk` package at
`vendor/@kourosh/sdk`. The browser package is version `0.1.0-alpha.1` and does
not require an npm registry publication.

```ts
invoke<TResult = unknown, TArgs extends JsonObject = JsonObject>(
  method: string,
  args: TArgs,
  options?: { timeoutMs?: number },
): Promise<TResult>
```

`invoke` validates method names, JSON arguments, and options before forwarding
to the bridge. `timeoutMs` is clamped to the bridge's bounded timeout policy.

```ts
import { invoke, KouroshError, PROTOCOL_VERSION } from "@kourosh/sdk";

try {
  const result = await invoke<{ message: string }>("greet", { name: "Akira" });
} catch (error) {
  if (error instanceof KouroshError) {
    console.error(error.code, error.message, error.requestId);
  }
}
```

`KouroshError` exposes `code`, `message`, optional `requestId`, and safe
`details`. `normalizeError` converts unknown thrown values into the same
shape. `PROTOCOL_VERSION` is `1`.

Common codes include `invalid_method`, `invalid_args`, `invalid_options`,
`bridge_unavailable`, `request_too_large`, `busy`, `timeout`,
`window_reloaded`, `window_closed`, `transport_error`, `method_not_allowed`,
and `python_error`.

The internal `window.kourosh` and `window.__kourosh*` functions are not stable
application APIs. Pending calls are rejected on timeout, transport failure,
window close, and renderer reload.
