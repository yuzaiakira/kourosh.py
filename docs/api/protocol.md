# RPC protocol v1

Protocol version 1 uses JSON request and response envelopes.

## Request

```json
{"protocol":1,"id":"request-1","method":"greet","args":{"name":"Akira"}}
```

`method` must match `[A-Za-z_][A-Za-z0-9_]{0,63}`. `args` is an object. The
Rust validator enforces trusted origins, registered methods, request size,
request ID validity, queue capacity, and timeout.

## Response

```json
{"protocol":1,"id":"request-1","ok":true,"result":{"message":"Hello Akira!"}}
```

```json
{"protocol":1,"id":"request-1","ok":false,"error":{"code":"python_error","message":"the Python handler raised an exception"}}
```

Unknown explicit protocol versions are rejected. Legacy envelopes without a
protocol field remain accepted for compatibility. Browser-side transport and
timeout failures may include `requestId`.

The protocol is a public alpha contract, not a 1.0 ABI. See [API stability](../api-stability.md).
