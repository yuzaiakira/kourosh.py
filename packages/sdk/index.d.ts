export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];
export type JsonObject = { [key: string]: JsonValue };

export interface InvokeOptions {
  timeoutMs?: number;
}

export interface KouroshErrorShape {
  code: string;
  message: string;
  requestId?: string;
  details?: JsonValue;
}

export class KouroshError extends Error {
  readonly code: string;
  readonly requestId?: string;
  readonly details?: JsonValue;
  constructor(error: KouroshErrorShape);
}

export function normalizeError(error: unknown, fallback?: string): KouroshErrorShape;

export function invoke<TResult = unknown, TArgs extends JsonObject = JsonObject>(
  method: string,
  args: TArgs,
  options?: InvokeOptions,
): Promise<TResult>;
