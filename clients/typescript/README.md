# @baalebos/ai

Official TypeScript/JavaScript client for the **Baalebos AI Gateway**. Works in Node.js (18+)
and in browsers — it only relies on the global `fetch` API, no Node-only dependencies.

## Install

```bash
cd clients/typescript
npm install
npm run build
```

This compiles `src/` into `dist/`, which is what gets imported.

## Configuration

In Node.js, the client can auto-discover config from environment variables:

```bash
export BAALEBOS_API_URL="https://<your-instance>.app.n8n.cloud/webhook/baalebos-ai"
export BAALEBOS_API_KEY="your-gateway-key"
```

In browsers (where `process.env` doesn't exist), or if you'd rather not rely on env vars,
pass config directly:

```ts
const client = new BaalebosAI({
  apiUrl: "https://<your-instance>.app.n8n.cloud/webhook/baalebos-ai",
  apiKey: "your-gateway-key",
});
```

## Usage

```ts
import { BaalebosAI } from "@baalebos/ai";

const client = new BaalebosAI(); // reads env vars in Node.js
const response = await client.chat("What is the capital of Nigeria?");
console.log(response);
```

`chat()` is always asynchronous (`await` it) — JavaScript's `fetch` is inherently async, so
there's no separate sync/async split like in the Python client.

### Options

```ts
await client.chat("Summarize this", {
  mode: "fast",        // "auto" | "fast" | "smart", default "auto"
  temperature: 0.7,     // default 0.7
});
```

## Error handling

Two distinct error types let you tell configuration problems apart from gateway/network
problems:

| Error | Thrown when |
|---|---|
| `BaalebosConfigError` | `apiUrl` or `apiKey` is missing (not in env vars and not passed to the constructor) |
| `BaalebosAPIError` | the gateway returned an error status, or the request couldn't be sent at all (check `.status`; `0` means a network-level failure rather than an HTTP response) |

```ts
import { BaalebosAI, BaalebosAPIError, BaalebosConfigError } from "@baalebos/ai";

try {
  const client = new BaalebosAI();
  console.log(await client.chat("Hello"));
} catch (err) {
  if (err instanceof BaalebosConfigError) {
    console.error("Missing config:", err.message);
  } else if (err instanceof BaalebosAPIError) {
    console.error(`Gateway error (${err.status}):`, err.message);
  } else {
    throw err;
  }
}
```

## Package structure

```
clients/typescript/
├── package.json
├── tsconfig.json
└── src/
    ├── index.ts   # public exports
    └── client.ts  # BaalebosAI client + error types
```
