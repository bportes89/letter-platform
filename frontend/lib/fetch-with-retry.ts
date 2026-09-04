const REQUEST_TIMEOUT_MS = 90_000;
const MAX_ATTEMPTS = 3;

function wait(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export async function fetchWithRetry(url: string, options: RequestInit = {}): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      window.clearTimeout(timer);
      return response;
    } catch (error) {
      window.clearTimeout(timer);
      lastError = error;
      if (attempt < MAX_ATTEMPTS - 1) {
        await wait(3000 * (attempt + 1));
      }
    }
  }
  throw lastError;
}
