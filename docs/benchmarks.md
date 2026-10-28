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

## Phase 2 Linux measurement

The Codex Cloud Linux 6.18.55 x86_64 runtime uses an Intel Xeon Platinum
8573C (5 visible CPUs), Python 3.12.14, Rust 1.99.1, and an optimized release
benchmark. With `KOUROSH_BENCH_SAMPLES=100` and
`KOUROSH_BENCH_CONCURRENCY=8`, one run after the Phase 2 runtime changes
measured:

| Measurement | Result |
| --- | ---: |
| Python runtime startup | 13.877 ms |
| RPC round trip p50 | 98 µs |
| RPC round trip p95 | 396 µs |
| RPC round trip p99 | 523 µs |
| Concurrent completed requests | 100 |
| Concurrent elapsed time | 13.225 ms |
| Concurrent throughput | 7,561.413 requests/s |

The Phase 1 run with the same parameters was 17.357 ms startup, 72/283/764
µs p50/p95/p99, and 6,593.768 requests/s. The Phase 2 run adds the native
method-registry path but still benchmarks the built-in `greet` handler, so this
single run is a comparison point rather than a performance conclusion.

Host startup and idle memory were not measured because the Linux host
intentionally exits with a WebView2-required message. These values are one
run on this cloud machine, not Windows claims or product guarantees.

## Phase 6 cloud measurement

On 2026-10-28, the same Linux cloud machine (Linux 6.18.55 x86_64, Intel Xeon
Platinum 8573C, 5 visible CPUs, Python 3.12.14, Rust 1.99.1, Node.js 24.19.0,
npm 11.9.0) produced the following single-run measurements. The Rust values
used the release benchmark with 100 samples and 8 workers; the other values
used the commands named below.

| Measurement | Result |
| --- | ---: |
| Embedded Python startup | 8.268 ms |
| RPC round trip p50 / p95 / p99 | 83 / 229 / 443 µs |
| Concurrent throughput | 10,308.078 requests/s |
| SDK wrapper overhead (`node scripts/bench-sdk.mjs`) | 1.372 µs/call |
| CLI `--version` startup | 151 ms |
| CLI `doctor --json` startup | 140 ms |
| Notes Vite production build | 1,452 ms |
| Notes `dist/` size | 149,903 bytes |
| Notes Vite readiness | 498 ms |

The Vite readiness command required the cloud command approval path because
the default sandbox denied loopback socket binding. The build itself completed
inside the default sandbox. No WebView2 startup, GUI interaction, Windows
working-set, or idle-memory value was measured.

## Phase 3 frontend measurements

On the same cloud runtime, a generated React JavaScript project was installed
with Node.js 24.19.0 and npm 11.9.0 before measuring. The production command
was `npm run build`; the development measurement started Vite on a randomly
allocated `127.0.0.1` port and polled `/` until it returned HTTP 200.
The repeatable commands are `scripts/bench-frontend.sh <project>` and
`node scripts/bench-sdk.mjs` after installing the generated project's local
dependencies.

| Measurement | Result |
| --- | ---: |
| Vite production build elapsed time | 2,577 ms |
| Vite output size (`dist/`) | 147,069 bytes |
| Vite dev server readiness | 1,230 ms |
| SDK wrapper samples | 10,000 |
| SDK wrapper overhead per call | 1.556 µs |

The SDK wrapper benchmark uses an in-process resolved bridge stub and therefore
does not represent WebView IPC or Python RPC latency. React and Node.js remain
development/build dependencies only; the production host serves the generated
static assets.

## Phase 4 packaging measurements

The portable packaging command now records artifact bytes in
`build-manifest.json` and emits a ZIP SHA-256 sidecar. No Windows package-size,
cold-start, WebView2 working-set, or idle-CPU measurement is claimed yet: the
current environment is Linux and has no runnable Windows host. Run
`scripts/package-smoke.ps1` on Windows, record the package directory and ZIP
sizes, cold start to the first visible window, the full process-tree working
set, and shutdown cleanup, then add the machine, Windows build, CPython,
WebView2, Rust profile, and commit SHA alongside the results.

On Windows, `scripts/bench.ps1 -Samples 1000 -Concurrency 8
-ResultsPath windows-benchmark-results.json` records internal RPC output,
process-tree and WebView2 working set, observed process startup, an idle CPU
sample, and shutdown duration. It labels visible-window timing as manual and
keeps internal RPC measurements separate from full WebView2 interaction. Do
not commit the JSON output when it contains machine-specific information.

## Phase 6 Linux regression checks

The Phase 6 developer workflow adds `scripts/bench-cli.sh`, which reports
wall-clock startup for `kourosh --version` and `kourosh doctor --json` in fresh
Python processes. `node scripts/bench-sdk.mjs` remains the SDK wrapper measure,
and `scripts/bench-frontend.sh examples/notes-react-ts` measures the real
React/TypeScript production build. These measurements exclude Windows GUI
startup and WebView2 memory, which remain platform-gated.

Run the tools from the repository root and record their output with the commit
SHA, OS/kernel, CPU, Python, Node, Rust profile, sample count, and concurrency.
Compare only runs made with the same methodology; a changed machine or build
profile is a new baseline rather than evidence of a regression.
