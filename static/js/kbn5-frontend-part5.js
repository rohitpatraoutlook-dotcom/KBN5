(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const money = value => "₹" + (Number(value || 0) / 100).toFixed(2);

  const panel = $("kbn5-orders-panel");
  if (!panel) return;

  const list = $("kbn5-orders-list");
  const details = $("kbn5-order-details");
  const statusMessage = $("kbn5-orders-message");

  let orders = [];
  let selectedOrder = null;
  let refreshHandle = null;

  const statusSteps = [
    { key: "placed", label: "Order placed", icon: "✓" },
    { key: "confirmed", label: "Order confirmed", icon: "✓" },
    { key: "stock_reserved", label: "Items reserved", icon: "▣" },
    { key: "picking_assigned", label: "Picker assigned", icon: "▣" },
    { key: "picking", label: "Items being picked", icon: "▣" },
    { key: "picked", label: "Items picked", icon: "✓" },
    { key: "packing", label: "Order being packed", icon: "▣" },
    { key: "ready_for_dispatch", label: "Ready for dispatch", icon: "⌁" },
    { key: "delivery_assigned", label: "Delivery partner assigned", icon: "⌁" },
    { key: "picked_up", label: "Order picked up", icon: "➜" },
    { key: "out_for_delivery", label: "Out for delivery", icon: "➜" },
    { key: "delivered", label: "Delivered", icon: "✓" }
  ];

  function normaliseStatus(value) {
    return String(value || "placed")
      .toLowerCase()
      .replace(/[\s-]+/g, "_");
  }

  function orderId(order) {
    return String(order.id ?? order.order_id ?? "");
  }

  function orderNumber(order) {
    return String(order.order_number ?? order.number ?? orderId(order));
  }

  function orderStatus(order) {
    return normaliseStatus(order.status ?? order.order_status ?? "placed");
  }

  function dateLabel(value) {
    if (!value) return "Date not available";
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? String(value)
      : date.toLocaleString("en-IN", {
          dateStyle: "medium",
          timeStyle: "short"
        });
  }

  function setMessage(message, error = false) {
    statusMessage.textContent = message;
    statusMessage.classList.toggle("is-error", error);
  }

  async function request(url) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" }
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.message || data.error || `Request failed (${response.status})`);
    }
    return data;
  }

  function orderRows(data) {
    if (Array.isArray(data)) return data;
    return data.orders || data.items || data.results || data.data || [];
  }

  function statusLabel(status) {
    const labels = {
      placed: "Order placed",
      pending: "Pending",
      confirmed: "Confirmed",
      accepted: "Confirmed",
      preparing: "Being prepared",
      processing: "Processing",
      packed: "Packed",
      ready_for_pickup: "Ready for delivery",
      out_for_delivery: "Out for delivery",
      dispatched: "Out for delivery",
      delivered: "Delivered",
      cancelled: "Cancelled",
      canceled: "Cancelled",
      failed: "Failed",
      returned: "Returned",
      refunded: "Refunded"
    };
    return labels[status] || status.replace(/_/g, " ");
  }

  function renderOrders() {
    list.replaceChildren();

    if (!orders.length) {
      const empty = document.createElement("div");
      empty.className = "kbn5-orders-empty";
      empty.innerHTML = "<span>🧾</span><h3>No orders found</h3><p>Your placed orders will appear here.</p>";
      list.appendChild(empty);
      return;
    }

    orders.forEach(order => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "kbn5-order-card";
      button.setAttribute("aria-pressed", orderId(order) === orderId(selectedOrder));

      const main = document.createElement("span");
      main.className = "kbn5-order-card-main";

      const title = document.createElement("strong");
      title.textContent = "Order #" + orderNumber(order);

      const date = document.createElement("small");
      date.textContent = dateLabel(order.created_at || order.createdAt || order.date);

      main.append(title, date);

      const side = document.createElement("span");
      side.className = "kbn5-order-card-side";

      const total = document.createElement("strong");
      total.textContent = money(order.total_paise ?? order.totalPaise ?? order.total);

      const status = document.createElement("small");
      status.className = "kbn5-status-pill";
      status.textContent = statusLabel(orderStatus(order));

      side.append(total, status);
      button.append(main, side);

      button.addEventListener("click", () => {
        selectedOrder = order;
        renderOrders();
        loadOrderDetails(order);
      });

      list.appendChild(button);
    });
  }

  function makeText(tag, text, className) {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    return element;
  }

  function renderTimeline(order) {
    const timeline = $("kbn5-order-timeline");
    timeline.replaceChildren();

    const status = orderStatus(order);
    const cancelled = ["cancelled", "canceled", "failed", "returned"].includes(status);

    const stepMap = {
      pending: 0,
      placed: 0,
      confirmed: 1,
      accepted: 1,
      processing: 2,
      preparing: 2,
      packed: 3,
      ready_for_pickup: 3,
      dispatched: 4,
      out_for_delivery: 4,
      delivered: 5
    };

    const activeIndex = stepMap[status] ?? 0;

    if (cancelled) {
      timeline.appendChild(
        makeText("div", statusLabel(status), "kbn5-timeline-cancelled")
      );
      timeline.appendChild(
        makeText("p", "Please check the order details or contact support for assistance.")
      );
      return;
    }

    statusSteps.forEach((step, index) => {
      const row = document.createElement("div");
      row.className = "kbn5-timeline-step";

      if (index < activeIndex) row.classList.add("is-complete");
      if (index === activeIndex) row.classList.add("is-current");

      const marker = makeText("span", index <= activeIndex ? "✓" : String(index + 1), "kbn5-timeline-marker");
      const text = document.createElement("span");
      text.className = "kbn5-timeline-text";
      text.appendChild(makeText("strong", step.label));

      if (index === activeIndex) {
        text.appendChild(makeText("small", "Current status"));
      }

      row.append(marker, text);
      timeline.appendChild(row);
    });
  }

  function renderOrderDetails(order) {
    details.hidden = false;
    $("kbn5-order-detail-number").textContent = "Order #" + orderNumber(order);
    $("kbn5-order-detail-date").textContent =
      "Placed: " + dateLabel(order.created_at || order.createdAt || order.date);
    $("kbn5-order-detail-status").textContent = statusLabel(orderStatus(order));
    $("kbn5-order-detail-total").textContent =
      money(order.total_paise ?? order.totalPaise ?? order.total);

    $("kbn5-order-payment-status").textContent =
      String(order.payment_status ?? order.paymentStatus ?? "Not provided")
        .replace(/_/g, " ");

    const address = order.delivery_address || order.address || "";
    $("kbn5-order-delivery-address").textContent =
      typeof address === "string" ? address :
      [address.address_line1, address.address_line2, address.city, address.pincode]
        .filter(Boolean).join(", ") || "Address details unavailable";

    renderTimeline(order);
  }

  async function loadOrderDetails(order) {
    details.hidden = false;
    $("kbn5-order-timeline").textContent = "Loading latest order status…";

    try {
      // Uses the existing order identifier; adjust if your backend uses another path.
      const data = await request(
        "/api/v1/orders/" + encodeURIComponent(orderId(order))
      );
      const fresh = data.order || data.data || data;
      selectedOrder = fresh;
      renderOrderDetails(fresh);
      setMessage("Order details updated.");
    } catch (_) {
      // Still display the order from the history response.
      renderOrderDetails(order);
      setMessage("Showing available order details. Latest status may need a refresh.");
    }
  }

  async function loadOrders() {
    setMessage("Loading your orders…");
    list.textContent = "Loading…";

    try {
      // If the orders blueprint uses a different history URL, change this endpoint.
      const data = await request("/api/v1/orders/");
      orders = orderRows(data);
      setMessage(orders.length ? "Your orders are ready." : "No orders to display.");
      renderOrders();

      if (selectedOrder) {
        const fresh = orders.find(order => orderId(order) === orderId(selectedOrder));
        if (fresh) {
          selectedOrder = fresh;
          renderOrderDetails(fresh);
        }
      } else if (orders.length) {
        selectedOrder = orders[0];
        renderOrders();
        await loadOrderDetails(selectedOrder);
      } else {
        details.hidden = true;
      }
    } catch (error) {
      list.replaceChildren();
      list.appendChild(makeText("p", "Could not load orders: " + error.message));
      setMessage("Sign in if required, then refresh your orders.", true);
    }
  }

  function openPanel() {
    $("kbn5-orders-panel").hidden = false;
    $("kbn5-orders-panel").classList.add("is-open");
    $("kbn5-orders-panel").setAttribute("aria-hidden", "false");
    document.body.classList.add("kbn5-orders-open");
    loadOrders();

    if (refreshHandle) clearInterval(refreshHandle);
    refreshHandle = setInterval(() => {
      if (!panel.hidden && selectedOrder) {
        loadOrderDetails(selectedOrder);
      }
    }, 30000);
  }

  function closePanel() {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    document.body.classList.remove("kbn5-orders-open");
    if (refreshHandle) clearInterval(refreshHandle);
    refreshHandle = null;
  }

  $("kbn5-orders-close").addEventListener("click", closePanel);
  $("kbn5-orders-refresh").addEventListener("click", loadOrders);

  document.addEventListener("click", event => {
    if (event.target.closest("[data-kbn5-open-orders]")) openPanel();
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closePanel();
  });

  window.addEventListener("kbn5:order-placed", () => {
    setTimeout(loadOrders, 800);
  });

  window.KBN5OrdersUI = {
    open: openPanel,
    close: closePanel,
    refresh: loadOrders
  };
})();
