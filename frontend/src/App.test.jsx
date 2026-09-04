import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";
import { DEMO_ORDERS } from "./demoOrders.js";

function response(body, ok = true, status = 200) {
  return { ok, status, statusText: ok ? "OK" : "Bad Request", json: async () => body };
}

function installFetch({ failingOrderId } = {}) {
  let calls = 0;
  globalThis.fetch = vi.fn(async (url, options = {}) => {
    calls += 1;
    if (url === "/health") return response({ status: "ok", model_name: "xgboost_baseline", expected_feature_count: 30, decision_threshold: 0.5 });
    const order = JSON.parse(options.body);
    if (order.order_id === failingOrderId) return response({ detail: "synthetic failure" }, false, 503);
    const score = (Number(order.order_id.slice(-3)) % 8) / 10 + 0.1;
    return response({ order_id: order.order_id, risk_score: score, decision_threshold: 0.5, predicted_delay: score >= 0.5, model_name: "xgboost_baseline" });
  });
  return () => calls;
}

describe("synthetic risk dashboard", () => {
  beforeEach(() => { vi.restoreAllMocks(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("loads metadata, makes one health plus eight prediction calls, and sorts risk", async () => {
    const callCount = installFetch();
    render(<App />);
    expect(await screen.findByText("xgboost_baseline")).toBeTruthy();
    expect(callCount()).toBe(9);
    const rows = screen.getAllByRole("row");
    expect(rows[1].textContent).toContain("demo-order-007");
    expect(screen.getByText("Risk score")).toBeTruthy();
    expect(screen.getByText("80.00%")).toBeTruthy();
  });

  it("supports search and all three filters", async () => {
    installFetch();
    render(<App />);
    await screen.findByText("demo-order-001");
    fireEvent.change(screen.getByLabelText("Search order ID"), { target: { value: "003" } });
    expect(screen.getByText("demo-order-003")).toBeTruthy();
    expect(screen.queryByText("demo-order-001")).toBeNull();
    fireEvent.change(screen.getByLabelText("Search order ID"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Filter predictions"), { target: { value: "predicted" } });
    expect(screen.getAllByText("Yes").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Filter predictions"), { target: { value: "notPredicted" } });
    expect(screen.getAllByText("No").length).toBeGreaterThan(0);
  });

  it("shows partial errors and retries failed requests", async () => {
    let fail = true;
    globalThis.fetch = vi.fn(async (url, options = {}) => {
      if (url === "/health") return response({ status: "ok", model_name: "xgboost_baseline", expected_feature_count: 30, decision_threshold: 0.5 });
      const order = JSON.parse(options.body);
      if (fail && order.order_id === "demo-order-001") return response({ detail: "offline" }, false, 503);
      return response({ order_id: order.order_id, risk_score: 0.6, decision_threshold: 0.5, predicted_delay: true, model_name: "xgboost_baseline" });
    });
    render(<App />);
    expect((await screen.findByRole("alert")).textContent).toContain("1 synthetic order request(s) failed");
    expect(screen.getByText("demo-order-002")).toBeTruthy();
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getAllByText("Yes")).toHaveLength(DEMO_ORDERS.length));
  });

  it("keeps the request source free of target and leakage fields", () => {
    expect(DEMO_ORDERS.every((order) => !("delay_flag" in order) && !("order_status" in order))).toBe(true);
    expect(Object.keys(DEMO_ORDERS[0])).toHaveLength(31);
  });
});
