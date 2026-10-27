/* KBN5 Operations UI — corrected routes and safe initialization */
(() => {
  "use strict";

  const API = {
    dashboard: "/api/v1/admin/operations/dashboard",
    warehouse: "/api/v1/admin/warehouse/orders/",
    deliveryMine: "/api/v1/delivery/my",
    partners: "/api/v1/admin/delivery-partners",
    assign: "/api/v1/admin/deliveries/assign",
    staff: "/api/v1/admin/staff/"
  };

  const $ = id => document.getElementById(id);

  async function request(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: {
        ...(options.body ? {"Content-Type": "application/json"} : {}),
        ...(options.headers || {})
      }
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || data.error || `HTTP ${response.status}`);
    }
    return data;
  }

  function message(text, error = false) {
    const el = $("kbn5-ops-message");
    if (el) {
      el.textContent = text;
      el.dataset.type = error ? "error" : "success";
    }
  }

  function list(data) {
    if (Array.isArray(data)) return data;
    return data.items || data.results || data.orders || data.staff || [];
  }

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
      "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
    })[c]);
  }

  async function loadDashboard() {
    try {
      const d = await request(API.dashboard);
      const s = d.summary || d.dashboard || d;
      const metrics = {
        "kbn5-ops-orders": s.total_orders ?? s.active_orders ?? s.orders_count,
        "kbn5-ops-picking": s.picking_orders ?? s.picking,
        "kbn5-ops-ready": s.ready_orders ?? s.ready_for_dispatch,
        "kbn5-ops-delivery": s.out_for_delivery ?? s.delivering,
        "kbn5-ops-staff": s.active_delivery_staff ?? s.active_staff,
        "kbn5-ops-products": s.total_products ?? s.products_count,
        "kbn5-ops-low-stock": s.low_stock_count,
        "kbn5-ops-customers": s.total_customers ?? s.customers_count
      };
      Object.entries(metrics).forEach(([id, value]) => {
        const el = $(id);
        if (el) el.textContent = value ?? "—";
      });
      message("Dashboard refreshed.");
      return d;
    } catch (e) {
      message("Dashboard: " + e.message, true);
      return null;
    }
  }

  async function loadWarehouse() {
    const container = $("kbn5-ops-warehouse-orders");
    if (!container) return;
    try {
      const data = await request(API.warehouse);
      const orders = list(data);
      if (!orders.length) {
        container.textContent = "No warehouse orders found.";
        return;
      }
      container.innerHTML = orders.map(o => {
        const id = Number(o.id ?? o.order_id ?? 0);
        const status = o.status || "confirmed";
        return `<article class="kbn5-ops-order">
          <strong>${esc(o.order_number || `Order #${id}`)}</strong>
          <span>${esc(status.replaceAll("_", " "))}</span>
          <button type="button" data-kbn5-advance="${id}">Advance stage</button>
        </article>`;
      }).join("");
      message("Warehouse orders loaded.");
    } catch (e) {
      message("Warehouse: " + e.message, true);
    }
  }

  async function advanceWarehouse(id) {
    try {
      await request(`${API.warehouse}${id}/advance`, {
        method: "POST",
        body: JSON.stringify({})
      });
      message(`Order #${id} advanced.`);
      await Promise.all([loadWarehouse(), loadDashboard()]);
    } catch (e) {
      message("Advance failed: " + e.message, true);
    }
  }

  async function loadStaff() {
    const container = $("kbn5-ops-staff-list");
    if (!container) return;
    try {
      const data = await request(API.staff);
      const staff = list(data);
      container.innerHTML = staff.length
        ? staff.map(s => `<div class="kbn5-ops-staff">
            <strong>${esc(s.name || s.full_name || s.email || `Staff #${s.id}`)}</strong>
            <span>${esc(s.role || "staff")}</span>
          </div>`).join("")
        : "<p>No staff found.</p>";
    } catch (e) {
      message("Staff: " + e.message, true);
    }
  }

  async function loadDeliveryAssignments() {
    const container = $("kbn5-ops-delivery-orders");
    if (!container) return;
    try {
      const [deliveryData, partnerData] = await Promise.all([
        request(API.deliveryMine),
        request(API.partners)
      ]);
      const deliveries = list(deliveryData);
      const partners = list(partnerData);
      container.innerHTML = deliveries.length
        ? deliveries.map(d => `<article class="kbn5-ops-order">
            <strong>Delivery #${esc(d.id ?? d.assignment_id)}</strong>
            <span>${esc(d.status || "assigned")}</span>
          </article>`).join("")
        : "<p>No delivery assignments returned for this account.</p>";

      const select = $("kbn5-ops-staff-select");
      if (select) {
        select.innerHTML = '<option value="">Select delivery partner</option>' +
          partners.map(p => `<option value="${Number(p.id)}">${esc(p.name || p.full_name || p.email || `Partner #${p.id}`)}</option>`).join("");
      }
    } catch (e) {
      message("Delivery data: " + e.message, true);
    }
  }

  async function assignDelivery() {
    const orderEl = $("kbn5-ops-assignment-order");
    const staffEl = $("kbn5-ops-staff-select");
    const orderId = Number(orderEl?.value);
    const staffId = Number(staffEl?.value);
    if (!orderId || !staffId) {
      message("Enter order ID and select a delivery partner.", true);
      return;
    }
    try {
      await request(API.assign, {
        method: "POST",
        body: JSON.stringify({order_id: orderId, delivery_partner_id: staffId})
      });
      message("Delivery assignment submitted.");
      await loadDashboard();
      await loadDeliveryAssignments();
    } catch (e) {
      message("Assignment failed: " + e.message, true);
    }
  }

  async function refresh() {
    await Promise.all([
      loadDashboard(),
      loadWarehouse(),
      loadStaff(),
      loadDeliveryAssignments()
    ]);
  }

  document.addEventListener("click", event => {
    const advance = event.target.closest("[data-kbn5-advance]");
    if (advance) advanceWarehouse(Number(advance.dataset.kbn5Advance));

    if (event.target.closest("#kbn5-ops-refresh")) refresh();
    if (event.target.closest("#kbn5-ops-close")) {
      const panel = $("kbn5-ops-panel");
      if (panel) panel.hidden = true;
    }
    if (event.target.closest("#kbn5-ops-toggle")) {
      const panel = $("kbn5-ops-panel");
      if (panel) {
        panel.hidden = !panel.hidden;
        if (!panel.hidden) refresh();
      }
    }
    if (event.target.closest("#kbn5-ops-assign")) assignDelivery();
  });

  window.KBN5OperationsUI = {
    loadDashboard,
    loadWarehouseOrders: loadWarehouse,
    loadStaff,
    loadDeliveryAssignments,
    refresh
  };
})();
