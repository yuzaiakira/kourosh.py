use kourosh_bridge::{AsyncDispatcher, RpcResponse, TRUSTED_ORIGIN};
use kourosh_python::PythonRuntime;
use std::env;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
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

    let startup = Instant::now();
    let runtime = Arc::new(PythonRuntime::new()?);
    println!(
        "python_runtime_startup_ms={:.3}",
        startup.elapsed().as_secs_f64() * 1000.0
    );

    let runtime_for_dispatch = Arc::clone(&runtime);
    let dispatcher = Arc::new(AsyncDispatcher::new(32, move |request| {
        runtime_for_dispatch.call(request)
    }));

    let mut latency_us = Vec::with_capacity(samples);
    for index in 0..samples {
        let raw = request(&format!("latency-{index}"));
        let started = Instant::now();
        let response = receive(&dispatcher, &raw);
        assert!(response.ok, "benchmark RPC failed: {:?}", response.error);
        latency_us.push(started.elapsed().as_micros());
    }
    println!("rpc_round_trip_us.p50={}", percentile(&mut latency_us, 50));
    println!("rpc_round_trip_us.p95={}", percentile(&mut latency_us, 95));
    println!("rpc_round_trip_us.p99={}", percentile(&mut latency_us, 99));

    let total = samples.max(concurrency);
    let next = Arc::new(AtomicUsize::new(0));
    let successes = Arc::new(AtomicUsize::new(0));
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
    let completed = successes.load(Ordering::Relaxed);
    println!("concurrent_requests={completed}");
    println!("concurrent_elapsed_ms={:.3}", elapsed * 1000.0);
    println!(
        "concurrent_requests_per_second={:.3}",
        completed as f64 / elapsed
    );

    dispatcher.shutdown();
    runtime.shutdown();
    Ok(())
}
