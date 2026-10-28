# Reliability and stress testing

The cloud-safe stress test exercises the real bounded Rust dispatcher and
asserts that active and queued counters return to zero:

```sh
KOUROSH_STRESS_REQUESTS=512 KOUROSH_STRESS_CONCURRENCY=16 ./scripts/stress.sh
```

The defaults are 256 requests and 8 workers. Each request uses the same JSON
validator, bounded queue, worker dispatch, and structured response path as the
native host. The test has a finite workload and does not start a service.

`scripts/stress.sh` also runs a bounded soak test. Select a finite mode with
`KOUROSH_STRESS_MODE=quick|standard|extended`; quick defaults to one second,
standard to five minutes, and extended to fifteen minutes. Override the
duration with `KOUROSH_SOAK_DURATION_MS` and worker count with
`KOUROSH_SOAK_CONCURRENCY`. The soak mixes burst traffic, queue overload, and
repeated calls with a bounded handler timeout, then shuts the dispatcher down
and waits for active/queued work to reach zero. It reports successes and
overload responses through Rust assertions; it does not claim that arbitrary
Python code can be terminated.

The dispatcher records accepted, rejected, completed, timeout, cancellation,
active, and queued counts. These counters are sampled directly by the Rust
tests and benchmark; no background monitoring thread is introduced. A timeout
test verifies that a cancellable Rust handler and an embedded Python handler
observe their token. It does not claim that arbitrary synchronous Python code
can be terminated.

On Linux, the benchmark samples `/proc/self/status`, `/proc/self/fd`, and
`/proc/self/task` before initialization, after warmup, during load, and after
cleanup. RSS can remain retained by the allocator after requests finish; a
stable active/queued count is cleanup evidence, not proof that the allocator
returned every page to the OS. Other platforms report unavailable OS fields.

The stress test is a component test, not a Windows GUI test. It does not
measure WebView2, native window responsiveness, or packaged process memory.
Use `scripts/bench.ps1` and `scripts/package-smoke.ps1` on a real Windows host
for those platform-specific measurements.
