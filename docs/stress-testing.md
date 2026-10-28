# Reliability and stress testing

The cloud-safe stress test exercises the real bounded Rust dispatcher and
asserts that active and queued counters return to zero:

```sh
KOUROSH_STRESS_REQUESTS=512 KOUROSH_STRESS_CONCURRENCY=16 ./scripts/stress.sh
```

The defaults are 256 requests and 8 workers. Each request uses the same JSON
validator, bounded queue, worker dispatch, and structured response path as the
native host. The test has a finite workload and does not start a service.

The dispatcher records accepted, rejected, completed, timeout, cancellation,
active, and queued counts. These counters are sampled directly by the Rust
tests and benchmark; no background monitoring thread is introduced. A timeout
test verifies that a cancellable handler observes its token. It does not claim
that arbitrary synchronous Python code can be terminated.

The stress test is a component test, not a Windows GUI test. It does not
measure WebView2, native window responsiveness, or packaged process memory.
Use `scripts/bench.ps1` and `scripts/package-smoke.ps1` on a real Windows host
for those platform-specific measurements.
