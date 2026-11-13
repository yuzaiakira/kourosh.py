# Known limitations

- Windows GUI and packaged-application execution have not run in Codex Cloud;
  WebView2 rendering and native event-loop behavior remain pending.
- The portable package and installer are not certified on a clean Windows
  machine. Code signing is not performed.
- A timed-out or closed request receives a structured browser error, but an
  already-running Python handler may continue. Cooperative cancellation does
  not roll back side effects and cannot forcibly terminate arbitrary Python
  threads.
- The current dispatcher uses one bridge worker and per-request handler
  threads. Python execution is serialized by the CPython GIL where applicable;
  a bounded worker-pool study is deferred to Phase 8B follow-up work.
- Linux `/proc` RSS values may remain elevated because of allocator retention;
  stable active/queued counters and file descriptors are cleanup evidence, not
  proof of leak freedom.
- Plugins are trusted in-process Python code. Metadata and registration are
  explicit, but plugins are not sandboxed.
- Protocol 1 accepts legacy requests without an explicit version for
  compatibility. Future protocol changes require an explicit compatibility
  decision.
- The alpha API can change. Private underscore methods, exact diagnostic
  messages, and the Rust `RuntimeAdapter` source contract are not 1.0 ABI
  guarantees.
