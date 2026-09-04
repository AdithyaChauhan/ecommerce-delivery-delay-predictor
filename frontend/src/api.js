async function readResponse(response, endpoint) {
  let body;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || "validation error").join(", ")
      : detail || response.statusText || "request failed";
    throw new Error(`${endpoint} failed (${response.status}): ${message}`);
  }
  return body;
}

export async function fetchHealth(signal) {
  return readResponse(await fetch("/health", { signal }), "/health");
}

export async function predictOrder(order, signal) {
  return readResponse(
    await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(order),
      signal,
    }),
    "/predict",
  );
}
