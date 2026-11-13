# HTML, CSS, and JavaScript

The vanilla template is ordinary static web content. Load the framework bridge
before application code:

```html
<script src="kourosh.js"></script>
<script src="app.js"></script>
```

Then call a registered Python method:

```js
const greeting = await window.kourosh.invoke("greet", { name: "Akira" });
```

Use a restrictive Content Security Policy. Keep the renderer on the trusted
local origin; the Rust host, not JavaScript, makes the final origin decision.

The browser bridge enforces a 64 KiB serialized request limit, at most 32
pending calls, a default five-second timeout, JSON-only values, and method
name validation. It rejects pending Promises when the transport closes or the
renderer reloads.

For the framework-independent typed wrapper, use the [JavaScript SDK
reference](../api/javascript.md). For development-server behavior, see
[Vite development](../vite-development.md).
