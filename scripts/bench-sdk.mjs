const samples = Math.max(1000, Number(process.env.KOUROSH_SDK_BENCH_SAMPLES || 10000));
globalThis.kourosh = { invoke: async (_method, args) => args };
const { invoke } = await import("../packages/sdk/index.js");
const started = process.hrtime.bigint();
for (let index = 0; index < samples; index += 1) {
  await invoke("noop", { index });
}
const elapsedNs = Number(process.hrtime.bigint() - started);
console.log(`sdk_wrapper_samples=${samples}`);
console.log(`sdk_wrapper_total_ms=${(elapsedNs / 1e6).toFixed(3)}`);
console.log(`sdk_wrapper_per_call_us=${(elapsedNs / samples / 1e3).toFixed(3)}`);
