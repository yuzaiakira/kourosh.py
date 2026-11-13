# JavaScript and TypeScript SDK

The official browser module is `@kourosh/sdk`. It is distributed with every
React template as a local `file:` dependency under
`vendor/@kourosh/sdk`; generated projects do not depend on this repository or
an unpublished npm package. The package contains JavaScript and declaration
files and is resolved by npm during frontend development.

The native bridge bootstrap remains a small browser script. It owns protocol
version `1`, request IDs, payload and pending-call limits, timeouts, structured
errors, and cleanup on `beforeunload`. Application code imports the typed
wrapper:

```ts
import { invoke } from "@kourosh/sdk";

type Greeting = { message: string };
const result = await invoke<Greeting>("greet", { name: "Akira" });
```

`KouroshError` preserves the bridge `code`, `message`, optional `requestId`, and
safe structured details. The wrapper rejects malformed method names, argument
containers, options, and non-JSON values before calling native code. The module
does not start Node.js, expose native capabilities, or evaluate code. A missing
bridge bootstrap produces `bridge_unavailable`.

The alpha browser package version is `0.1.0-alpha.1`. Its public contract is
the typed `invoke` function, `KouroshError`, and `normalizeError`. The protocol
remains version 1; pending calls are rejected on timeout, transport failure,
window close, and renderer reload. Internal `window.kourosh` and
`window.__kourosh*` hooks are implementation details.

The module is framework-independent and can be used by React, Vue, Svelte, or
plain TypeScript frontends. Only React and React+TypeScript templates are
generated in this phase.
