const REQUEST_TIMEOUT_MS = 90_000;
const MAX_ATTEMPTS = 3;

export type FetchRetryOptions = {
  timeoutMs?: number;
  maxAttempts?: number;
};

function wait(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  retry: FetchRetryOptions = {},
): Promise<Response> {
  const timeoutMs = retry.timeoutMs ?? REQUEST_TIMEOUT_MS;
  const maxAttempts = retry.maxAttempts ?? MAX_ATTEMPTS;
  let lastError: unknown;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      window.clearTimeout(timer);
      return response;
    } catch (error) {
      window.clearTimeout(timer);
      lastError = error;
      if (attempt < maxAttempts - 1) {
        await wait(3000 * (attempt + 1));
      }
    }
  }
  throw lastError;
}
