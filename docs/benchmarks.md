# Local runtime benchmarks

Run `scripts/bench.sh` on Linux/macOS or `scripts/bench.ps1` on Windows. The
Rust benchmark initializes embedded CPython, measures `greet` RPC round trips,
and drives the bounded dispatcher from multiple threads. It prints p50/p95/p99
latency in microseconds, interpreter startup time, completed request count,
elapsed time, and throughput. `KOUROSH_BENCH_SAMPLES` and
`KOUROSH_BENCH_CONCURRENCY` control the sample count and worker count.

The Windows script also starts the release host, observes process startup and
working-set memory after two seconds, and closes the window. Those host values
include WebView2 child processes only in a Windows environment where they can
be inspected; the Linux script explicitly reports those measurements as
unavailable.

Measurements are evidence for the named machine and build, not product
promises. Record OS build, CPU, Python version, WebView2 version, Rust profile,
sample count, and concurrency beside any result used for a regression decision.

## Current Linux measurement

The Codex Cloud Linux x86_64 runtime uses Python 3.12.14, Rust 1.99.1, and an
optimized release benchmark. With `KOUROSH_BENCH_SAMPLES=100` and
`KOUROSH_BENCH_CONCURRENCY=8`, one run measured:

| Measurement | Result |
| --- | ---: |
| Python runtime startup | 17.357 ms |
| RPC round trip p50 | 72 µs |
| RPC round trip p95 | 283 µs |
| RPC round trip p99 | 764 µs |
| Concurrent completed requests | 100 |
| Concurrent elapsed time | 15.166 ms |
| Concurrent throughput | 6,593.768 requests/s |

Host startup and idle memory were not measured because the Linux host
intentionally exits with a WebView2-required message. These values are one
run on this cloud machine, not Windows claims or product guarantees.
