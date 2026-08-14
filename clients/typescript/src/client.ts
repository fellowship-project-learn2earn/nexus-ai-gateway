/**
 * Core SDK for the Baalebos AI Gateway.
 * Mirrors clients/python/baalebos_ai/client.py:
 *  - auto env var discovery (BAALEBOS_API_URL / BAALEBOS_API_KEY)
 *  - clear, immediate errors when config is missing
 *  - same request/response shape as the gateway spec
 *
 * Works in Node.js (18+) and in browsers, since it only relies on
 * the global `fetch` API - no Node-only dependencies.
 */

export interface BaalebosOptions {
  apiUrl?: string;
  apiKey?: string;
}

export interface ChatOptions {
  mode?: 'auto' | 'fast' | 'smart';
  temperature?: number;
}

/** Thrown when apiUrl/apiKey are missing - mirrors the Python ValueError. */
export class BaalebosConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'BaalebosConfigError';
  }
}

/** Thrown when the gateway itself returns an error response (401, 5xx, etc). */
export class BaalebosAPIError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'BaalebosAPIError';
    this.status = status;
  }
}

// process.env only exists in Node - guard so this doesn't crash in a browser bundle.
function readEnv(name: string): string | undefined {
  if (typeof process !== 'undefined' && process.env) {
    return process.env[name];
  }
  return undefined;
}

export class BaalebosAI {
  private apiUrl: string;
  private apiKey: string;

  constructor(options: BaalebosOptions = {}) {
    const apiUrl = options.apiUrl ?? readEnv('BAALEBOS_API_URL');
    const apiKey = options.apiKey ?? readEnv('BAALEBOS_API_KEY');

    if (!apiUrl) {
      throw new BaalebosConfigError(
        'BAALEBOS_API_URL is missing. Set the environment variable or pass apiUrl to the constructor.'
      );
    }
    if (!apiKey) {
      throw new BaalebosConfigError(
        'BAALEBOS_API_KEY is missing. Set the environment variable or pass apiKey to the constructor.'
      );
    }

    this.apiUrl = apiUrl;
    this.apiKey = apiKey;
  }

  /**
   * Send a prompt to the gateway and return the reply text.
   * Always async, since fetch is async in both Node and browsers -
   * there's no separate "sync" mode like in the Python client.
   */
  async chat(prompt: string, options: ChatOptions = {}): Promise<string> {
    const { mode = 'auto', temperature = 0.7 } = options;

    let response: Response;
    try {
      response = await fetch(this.apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': this.apiKey,
        },
        body: JSON.stringify({ message: prompt, mode, temperature }),
      });
    } catch (err) {
      throw new BaalebosAPIError(
        `Network error reaching Baalebos gateway: ${(err as Error).message}`,
        0
      );
    }

    if (!response.ok) {
      throw new BaalebosAPIError(
        `Baalebos gateway returned ${response.status} ${response.statusText}`,
        response.status
      );
    }

    const data: any = await response.json();

    if (data?.data?.choices?.[0]?.message?.content) {
      return data.data.choices[0].message.content;
    }
    if (data?.output) {
      return data.output;
    }
    return JSON.stringify(data);
  }
}
