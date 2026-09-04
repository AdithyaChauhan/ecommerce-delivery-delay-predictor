import { useEffect, useMemo, useState } from "react";
import { fetchHealth, predictOrder } from "./api.js";
import { DEMO_ORDERS } from "./demoOrders.js";

const FILTERS = {
  all: "All",
  predicted: "Predicted delay",
  notPredicted: "Not predicted delay",
};

function formatRisk(score) {
  return `${(score * 100).toFixed(2)}%`;
}

function formatDistance(distance) {
  return distance == null ? "—" : `${Number(distance).toFixed(1)} km`;
}

export default function App() {
  const [metadata, setMetadata] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    async function load() {
      setState("loading");
      setError("");
      setPredictions([]);
      try {
        const health = await fetchHealth(controller.signal);
        if (!active) return;
        setMetadata(health);
        const results = await Promise.allSettled(
          DEMO_ORDERS.map((order) => predictOrder(order, controller.signal)),
        );
        if (!active) return;
        const successful = [];
        const failures = [];
        results.forEach((result, index) => {
          if (result.status === "fulfilled") {
            successful.push({ ...DEMO_ORDERS[index], prediction: result.value });
          } else if (result.reason?.name !== "AbortError") {
            failures.push(`${DEMO_ORDERS[index].order_id}: ${result.reason?.message || "request failed"}`);
          }
        });
        successful.sort((left, right) => {
          const scoreDifference = right.prediction.risk_score - left.prediction.risk_score;
          return scoreDifference || left.order_id.localeCompare(right.order_id);
        });
        setPredictions(successful);
        if (failures.length === DEMO_ORDERS.length) {
          setState("error");
          setError(`All prediction requests failed. ${failures.join("; ")}`);
        } else if (failures.length > 0) {
          setState("partial");
          setError(`${failures.length} synthetic order request(s) failed. Retry to try again.`);
        } else {
          setState("ready");
        }
      } catch (caught) {
        if (!active || caught.name === "AbortError") return;
        setState("error");
        setError(caught.message || "The API could not be reached.");
      }
    }

    load();
    return () => {
      active = false;
      controller.abort();
    };
  }, [retryToken]);

  const visiblePredictions = useMemo(() => {
    const query = search.trim().toLowerCase();
    return predictions.filter(({ order_id, prediction }) => {
      const matchesSearch = !query || order_id.toLowerCase().includes(query);
      const matchesFilter = filter === "all"
        || (filter === "predicted" && prediction.predicted_delay)
        || (filter === "notPredicted" && !prediction.predicted_delay);
      return matchesSearch && matchesFilter;
    });
  }, [filter, predictions, search]);

  const predictedCount = predictions.filter(({ prediction }) => prediction.predicted_delay).length;

  return (
    <main className="dashboard">
      <header className="hero">
        <p className="eyebrow">Synthetic demo data</p>
        <h1>Delivery delay risk</h1>
        <p>Historical 2016–2018 demonstration using the local Gold-v1 model.</p>
      </header>

      <section className="summary" aria-label="Prediction summary">
        <div className="card"><span>Total synthetic orders</span><strong>{DEMO_ORDERS.length}</strong></div>
        <div className="card"><span>Successfully scored</span><strong>{predictions.length}</strong></div>
        <div className="card"><span>Predicted delays</span><strong>{predictedCount}</strong></div>
        <div className="card"><span>Model</span><strong>{metadata?.model_name || "—"}</strong><small>Threshold: {metadata ? formatRisk(metadata.decision_threshold) : "—"}</small></div>
      </section>

      {state === "loading" && <p className="notice" role="status">Loading synthetic orders and risk scores…</p>}
      {error && <div className={`notice error ${state === "partial" ? "partial" : ""}`} role="alert"><span>{error}</span><button type="button" onClick={() => setRetryToken((value) => value + 1)}>Retry</button></div>}

      {state !== "loading" && predictions.length === 0 && !error && <p className="notice" role="status">No predictions to display.</p>}

      <section className="results" aria-label="Synthetic order predictions">
        <div className="controls">
          <label htmlFor="order-search">Search order ID
            <input id="order-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="demo-order-001" />
          </label>
          <label htmlFor="prediction-filter">Filter predictions
            <select id="prediction-filter" value={filter} onChange={(event) => setFilter(event.target.value)}>
              <option value="all">{FILTERS.all}</option>
              <option value="predicted">{FILTERS.predicted}</option>
              <option value="notPredicted">{FILTERS.notPredicted}</option>
            </select>
          </label>
        </div>
        <div className="table-wrap">
          <table>
            <caption>Every row is synthetic demo data; scores are delivery-delay risk scores.</caption>
            <thead><tr><th scope="col">Order ID</th><th scope="col">Customer state</th><th scope="col">Product category</th><th scope="col">Seller state</th><th scope="col">Item rows</th><th scope="col">Max seller/customer distance</th><th scope="col">Risk score</th><th scope="col">Predicted delay</th></tr></thead>
            <tbody>
              {visiblePredictions.map(({ order_id, customer_state, primary_product_category, primary_seller_state, item_row_count, seller_customer_distance_km_max, prediction }) => (
                <tr key={order_id}>
                  <td>{order_id}<small>Synthetic demo</small></td>
                  <td>{customer_state}</td><td>{primary_product_category}</td><td>{primary_seller_state}</td><td>{item_row_count}</td><td>{formatDistance(seller_customer_distance_km_max)}</td><td>{formatRisk(prediction.risk_score)}</td><td><span className={prediction.predicted_delay ? "badge late" : "badge on-time"}>{prediction.predicted_delay ? "Yes" : "No"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {state !== "loading" && predictions.length > 0 && visiblePredictions.length === 0 && <p className="notice" role="status">No synthetic orders match the current search and filter.</p>}
      </section>
    </main>
  );
}
