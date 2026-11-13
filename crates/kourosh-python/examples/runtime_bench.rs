use kourosh_bridge::{AsyncDispatcher, MetricsMode, ResourceSnapshot, RpcResponse, TRUSTED_ORIGIN};
use kourosh_python::{PythonRuntime, RuntimeAdapter};
use serde_json::{json, Value};
use std::env;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

fn request(id: &str) -> String {
    serde_json::json!({
        "id": id,
        "method": "greet",
        "args": {"name": "Bench"}
    })
    .to_string()
}

fn percentile(values: &mut [u128], percentile: usize) -> u128 {
    values.sort_unstable();
    let index = ((values.len() - 1) * percentile) / 100;
    values[index]
}

fn receive(dispatcher: &AsyncDispatcher, raw: &str) -> RpcResponse {
    dispatcher
        .submit(raw, TRUSTED_ORIGIN, Duration::from_secs(5))
        .expect("benchmark request should fit the bounded dispatcher")
        .recv()
        .expect("benchmark response should arrive")
}

fn resource(dispatcher: &AsyncDispatcher, label: &str) -> Value {
    let active = dispatcher.active_requests();
    serde_json::to_value(ResourceSnapshot::capture(
        active,
        dispatcher.queued_requests(),
        active,
    ))
    .map(|snapshot| json!({"label": label, "sample": snapshot}))
    .expect("resource snapshot is serializable")
}

fn cpu_model() -> Option<String> {
    #[cfg(target_os = "linux")]
    {
        std::fs::read_to_string("/proc/cpuinfo")
            .ok()
            .and_then(|contents| {
                contents.lines().find_map(|line| {
                    line.strip_prefix("model name\t: ")
                        .or_else(|| line.strip_prefix("Hardware\t: "))
                        .map(str::to_owned)
                })
            })
    }
    #[cfg(not(target_os = "linux"))]
    {
        None
    }
}

fn env_or_unknown(name: &str) -> String {
    env::var(name).unwrap_or_else(|_| "unknown".to_owned())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let samples = env::var("KOUROSH_BENCH_SAMPLES")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(200)
        .max(10);
    let concurrency = env::var("KOUROSH_BENCH_CONCURRENCY")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(8)
        .max(1);
    let warmup = env::var("KOUROSH_BENCH_WARMUP")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(50)
        .min(100_000);
    let metrics_mode = if env::var("KOUROSH_BENCH_METRICS").as_deref() == Ok("disabled") {
        MetricsMode::Disabled
    } else {
        MetricsMode::Enabled
    };
    let metrics_mode_name = match metrics_mode {
        MetricsMode::Enabled => "enabled",
        MetricsMode::Disabled => "disabled",
    };

    let before_initialization = ResourceSnapshot::capture(0, 0, 0);
    let startup = Instant::now();
    let runtime = Arc::new(PythonRuntime::new()?);
    let capabilities = runtime.capabilities();
    let startup_ms = startup.elapsed().as_secs_f64() * 1000.0;
    println!("python_runtime_startup_ms={startup_ms:.3}");
    println!(
        "runtime_adapter={} protocol={} init_measurement_ms={:.3}",
        capabilities.runtime_id,
        capabilities.protocol_version,
        capabilities.initialization_duration.as_secs_f64() * 1000.0
    );

    let runtime_for_dispatch = Arc::clone(&runtime);
    let dispatcher = Arc::new(AsyncDispatcher::new_cancellable_with_metrics(
        32,
        metrics_mode,
        move |request, cancellation| {
            runtime_for_dispatch.dispatch_with_cancellation(request, &cancellation)
        },
    ));
    let after_initialization = resource(&dispatcher, "after_initialization");

    for index in 0..warmup {
        let response = receive(&dispatcher, &request(&format!("warmup-{index}")));
        assert!(response.ok, "warmup RPC failed: {:?}", response.error);
    }
    let after_warmup = resource(&dispatcher, "after_warmup");

    let mut latency_us = Vec::with_capacity(samples);
    for index in 0..samples {
        let raw = request(&format!("latency-{index}"));
        let started = Instant::now();
        let response = receive(&dispatcher, &raw);
        assert!(response.ok, "benchmark RPC failed: {:?}", response.error);
        latency_us.push(started.elapsed().as_micros());
    }
    let p50 = percentile(&mut latency_us, 50);
    let p95 = percentile(&mut latency_us, 95);
    let p99 = percentile(&mut latency_us, 99);
    println!("rpc_round_trip_us.p50={p50}");
    println!("rpc_round_trip_us.p95={p95}");
    println!("rpc_round_trip_us.p99={p99}");

    let total = samples.max(concurrency);
    let next = Arc::new(AtomicUsize::new(0));
    let successes = Arc::new(AtomicUsize::new(0));
    let collecting = Arc::new(AtomicBool::new(true));
    let resource_points = Arc::new(Mutex::new(vec![
        json!({"label": "before_initialization", "sample": before_initialization}),
        after_initialization,
        after_warmup,
    ]));
    let sampler_dispatcher = Arc::clone(&dispatcher);
    let sampler_collecting = Arc::clone(&collecting);
    let sampler_points = Arc::clone(&resource_points);
    let sampler = thread::Builder::new()
        .name("kourosh-bench-sampler".to_owned())
        .spawn(move || {
            while sampler_collecting.load(Ordering::Acquire) {
                thread::sleep(Duration::from_millis(10));
                if sampler_collecting.load(Ordering::Acquire) {
                    sampler_points
                        .lock()
                        .expect("benchmark resource mutex is not poisoned")
                        .push(resource(&sampler_dispatcher, "during_load"));
                }
            }
        })?;
    resource_points
        .lock()
        .expect("benchmark resource mutex is not poisoned")
        .push(resource(&dispatcher, "load_start"));
    let started = Instant::now();
    let mut workers = Vec::with_capacity(concurrency);
    for worker_index in 0..concurrency {
        let dispatcher = Arc::clone(&dispatcher);
        let next = Arc::clone(&next);
        let successes = Arc::clone(&successes);
        workers.push(thread::spawn(move || loop {
            let index = next.fetch_add(1, Ordering::Relaxed);
            if index >= total {
                break;
            }
            let raw = request(&format!("throughput-{worker_index}-{index}"));
            let response = receive(&dispatcher, &raw);
            if response.ok {
                successes.fetch_add(1, Ordering::Relaxed);
            }
        }));
    }
    for worker in workers {
        worker.join().expect("benchmark worker should not panic");
    }
    let elapsed = started.elapsed().as_secs_f64();
    collecting.store(false, Ordering::Release);
    sampler.join().expect("benchmark sampler should not panic");
    resource_points
        .lock()
        .expect("benchmark resource mutex is not poisoned")
        .push(resource(&dispatcher, "load_end"));
    let completed = successes.load(Ordering::Relaxed);
    let throughput = completed as f64 / elapsed;
    println!("concurrent_requests={completed}");
    println!("concurrent_elapsed_ms={:.3}", elapsed * 1000.0);
    println!("concurrent_requests_per_second={throughput:.3}");

    let metrics = dispatcher.metrics();
    println!("dispatcher_accepted={}", metrics.accepted);
    println!("dispatcher_rejected={}", metrics.rejected);
    println!("dispatcher_timeouts={}", metrics.timeouts);
    println!("dispatcher_active={}", dispatcher.active_requests());
    println!("dispatcher_queued={}", dispatcher.queued_requests());
    dispatcher.shutdown();
    runtime.shutdown();
    let cleanup_deadline = Instant::now() + Duration::from_secs(5);
    while dispatcher.active_requests() > 0 && Instant::now() < cleanup_deadline {
        thread::sleep(Duration::from_millis(2));
    }
    resource_points
        .lock()
        .expect("benchmark resource mutex is not poisoned")
        .push(resource(&dispatcher, "after_cleanup"));

    let report = json!({
        "schema": 2,
        "benchmark": "embedded-python-rpc",
        "benchmark_version": "phase8a",
        "commit": env_or_unknown("KOUROSH_BENCH_COMMIT"),
        "os": env::consts::OS,
        "architecture": env::consts::ARCH,
        "cpu": cpu_model(),
        "rust": env_or_unknown("KOUROSH_RUST_VERSION"),
        "python": env_or_unknown("KOUROSH_PYTHON_VERSION"),
        "profile": "release",
        "samples": samples,
        "concurrency": concurrency,
        "warmup": warmup,
        "metrics": metrics_mode_name,
        "startup_ms": startup_ms,
        "runtime_init_ms": capabilities.initialization_duration.as_secs_f64() * 1000.0,
        "latency_us": {"p50": p50, "p95": p95, "p99": p99},
        "throughput": {
            "requests": completed,
            "elapsed_ms": elapsed * 1000.0,
            "requests_per_second": throughput,
        },
        "dispatcher": {
            "accepted": metrics.accepted,
            "rejected": metrics.rejected,
            "completed": metrics.completed,
            "timeouts": metrics.timeouts,
            "canceled": metrics.canceled,
            "active_after_cleanup": dispatcher.active_requests(),
            "queued_after_cleanup": dispatcher.queued_requests(),
        },
        "resources": resource_points
            .lock()
            .expect("benchmark resource mutex is not poisoned")
            .clone(),
        "methodology": "release build; bounded queue; warmup before latency; independent process run; /proc resource samples on Linux",
    });
    let serialized = serde_json::to_string(&report)?;
    println!("benchmark_report_json={serialized}");
    if let Ok(path) = env::var("KOUROSH_BENCH_REPORT") {
        std::fs::write(path, format!("{serialized}\n"))?;
    }
    Ok(())
}
