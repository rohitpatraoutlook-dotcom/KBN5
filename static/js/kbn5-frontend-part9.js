/* KBN5 Operations Dashboard — Part 9 */
(() => {
  "use strict";

  const API = {
    dashboard: "/api/v1/operations/dashboard/",
    warehouseOrders: "/api/v1/warehouse/orders/",
    deliveryOrders: "/api/v1/delivery/orders/",
    staff: "/api/v1/admin/staff/"
  };

  const $ = (id) => document.getElementById(id);

  async function request(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      },
      ...options
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.message || data.error || `Request failed (${response.status})`);
    }

    return data;
  }

  function getList(data) {
    if (Array.isArray(data)) return data;
    return data.results || data.items || data.orders || data.staff || [];
  }

  function showMessage(message, error = false) {
    const el = $("kbn5-ops-message");
    if (!el) return;
    el.textContent = message;
    el.dataset.type = error ? "error" : "success";
  }

  function money(value) {
    const amount = Number(value || 0);
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2
    }).format(amount / 100);
  }

  function setMetric(id, value) {
    const el = $(id);
    if (el) el.textContent = value ?? "—";
  }

  function safeText(value) {
    return String(value ?? "");
  }

  async function loadDashboard() {
    try {
      const data = await request(API.dashboard);
      const summary = data.summary || data.dashboard || data;

      setMetric("kbn5-ops-orders", summary.total_orders ?? summary.orders_count);
      setMetric("kbn5-ops-picking", summary.picking_orders ?? summary.picking);
      setMetric("kbn5-ops-ready", summary.ready_orders ?? summary.ready);
      setMetric("kbn5-ops-delivery", summary.out_for_delivery ?? summary.delivering);
      setMetric("kbn5-ops-staff", summary.active_delivery_staff ?? summary.active_staff);

      showMessage("Operations summary loaded.");
      return data;
    } catch (error) {
      showMessage("Dashboard: " + error.message, true);
      return null;
    }
  }

  window.KBN5OperationsUI = {
    loadDashboard
  };
})();

/* Warehouse order management */

function renderWarehouseOrders(data) {
  const container = document.getElementById("kbn5-ops-warehouse-orders");
  if (!container) return;

  const orders = getList(data);

  if (!orders.length) {
    container.innerHTML = '<p class="kbn5-ops-empty">No warehouse orders found.</p>';
    return;
  }

  container.innerHTML = orders.map((order) => {
    const id = order.id ?? order.order_id ?? "";
    const number = order.order_number || `Order #${id}`;
    const status = order.status || order.fulfillment_status || "pending";
    const items = order.items_count ?? order.item_count ?? "—";

    return `
      <article class="kbn5-ops-order" data-order-id="${Number(id) || 0}">
        <div class="kbn5-ops-order-info">
          <strong>${escapeHTML(number)}</strong>
          <span>${escapeHTML(status.replaceAll("_", " "))}</span>
          <small>Items: ${escapeHTML(items)}</small>
        </div>
        <label>
          Update status
          <select class="kbn5-ops-warehouse-status">
            ${["pending", "picking", "packed", "ready", "completed"].map(s =>
              `<option value="${s}" ${s === status ? "selected" : ""}>${s}</option>`
            ).join("")}
          </select>
        </label>
        <button type="button" class="kbn5-ops-save-warehouse"
          data-id="${Number(id) || 0}">Save</button>
      </article>`;
  }).join("");
}

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);
}

async function loadWarehouseOrders() {
  try {
    const data = await request(API.warehouseOrders);
    renderWarehouseOrders(data);
    showMessage("Warehouse orders loaded.");
  } catch (error) {
    showMessage("Warehouse orders: " + error.message, true);
  }
}

async function updateWarehouseOrder(id, status) {
  try {
    await request(`${API.warehouseOrders}${encodeURIComponent(id)}/`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    });

    showMessage(`Order #${id} updated.`);
    await loadWarehouseOrders();
    await loadDashboard();
  } catch (error) {
    showMessage("Could not update order: " + error.message, true);
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest(".kbn5-ops-save-warehouse");
  if (!button) return;

  const card = button.closest(".kbn5-ops-order");
  const select = card?.querySelector(".kbn5-ops-warehouse-status");
  const id = Number(button.dataset.id);

  if (!id || !select) {
    showMessage("Order ID is missing.", true);
    return;
  }

  updateWarehouseOrder(id, select.value);
});

window.KBN5OperationsUI.loadWarehouseOrders = loadWarehouseOrders;

/* Delivery assignment management */

function renderDeliveryOrders(data) {
  const container = document.getElementById("kbn5-ops-delivery-orders");
  if (!container) return;

  const orders = getList(data);

  if (!orders.length) {
    container.innerHTML = '<p class="kbn5-ops-empty">No delivery orders found.</p>';
    return;
  }

  container.innerHTML = orders.map((order) => {
    const id = Number(order.id ?? order.order_id ?? 0);
    const number = order.order_number || `Order #${id}`;
    const status = order.status || "ready";
    const staffId = order.delivery_staff_id ?? order.assigned_staff_id ?? "";

    return `
      <article class="kbn5-ops-order">
        <div class="kbn5-ops-order-info">
          <strong>${escapeHTML(number)}</strong>
          <span>Status: ${escapeHTML(status.replaceAll("_", " "))}</span>
          <small>Assigned staff: ${escapeHTML(staffId || "Unassigned")}</small>
        </div>
        <label>
          Delivery status
          <select class="kbn5-ops-delivery-status">
            ${["ready", "assigned", "picked_up", "out_for_delivery", "delivered", "failed"].map(s =>
              `<option value="${s}" ${s === status ? "selected" : ""}>${s.replaceAll("_", " ")}</option>`
            ).join("")}
          </select>
        </label>
        <button type="button" class="kbn5-ops-save-delivery"
          data-id="${id}">Update</button>
      </article>`;
  }).join("");
}

async function loadDeliveryOrders() {
  try {
    const data = await request(API.deliveryOrders);
    renderDeliveryOrders(data);
    showMessage("Delivery orders loaded.");
  } catch (error) {
    showMessage("Delivery orders: " + error.message, true);
  }
}

async function updateDeliveryOrder(id, status) {
  try {
    await request(`${API.deliveryOrders}${encodeURIComponent(id)}/`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    });

    showMessage(`Delivery order #${id} updated.`);
    await loadDeliveryOrders();
    await loadDashboard();
  } catch (error) {
    showMessage("Delivery update failed: " + error.message, true);
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest(".kbn5-ops-save-delivery");
  if (!button) return;

  const card = button.closest(".kbn5-ops-order");
  const select = card?.querySelector(".kbn5-ops-delivery-status");
  const id = Number(button.dataset.id);

  if (!id || !select) {
    showMessage("Delivery order ID is missing.", true);
    return;
  }

  updateDeliveryOrder(id, select.value);
});

window.KBN5OperationsUI.loadDeliveryOrders = loadDeliveryOrders;

/* Delivery staff and order assignment */

async function loadDeliveryStaff() {
  const select = document.getElementById("kbn5-ops-staff-select");
  const container = document.getElementById("kbn5-ops-staff-list");

  try {
    const data = await request(API.staff);
    const staff = getList(data);

    if (select) {
      select.innerHTML = '<option value="">Select delivery staff</option>' +
        staff.map((person) => {
          const id = person.id ?? person.user_id;
          const name = person.name || person.full_name ||
            person.username || person.email || `Staff ${id}`;

          return `<option value="${Number(id) || 0}">${escapeHTML(name)}</option>`;
        }).join("");
    }

    if (container) {
      container.innerHTML = staff.length
        ? staff.map((person) => {
            const id = person.id ?? person.user_id;
            const name = person.name || person.full_name ||
              person.username || person.email || `Staff ${id}`;
            const active = person.is_active ?? person.active ?? true;

            return `
              <article class="kbn5-ops-staff">
                <strong>${escapeHTML(name)}</strong>
                <span>${active ? "Active" : "Inactive"}</span>
                <small>${escapeHTML(person.phone || person.email || "")}</small>
              </article>`;
          }).join("")
        : '<p class="kbn5-ops-empty">No staff found.</p>';
    }

    showMessage("Delivery staff loaded.");
  } catch (error) {
    showMessage("Staff list: " + error.message, true);
  }
}

async function assignDeliveryStaff() {
  const orderInput = document.getElementById("kbn5-ops-assignment-order");
  const staffSelect = document.getElementById("kbn5-ops-staff-select");

  const orderId = Number(orderInput?.value);
  const staffId = Number(staffSelect?.value);

  if (!orderId || !staffId) {
    showMessage("Enter an order ID and select delivery staff.", true);
    return;
  }

  try {
    await request(
      `${API.deliveryOrders}${encodeURIComponent(orderId)}/assign/`,
      {
        method: "POST",
        body: JSON.stringify({ staff_id: staffId })
      }
    );

    showMessage(`Staff assigned to order #${orderId}.`);
    if (orderInput) orderInput.value = "";

    await Promise.all([
      loadDeliveryOrders(),
      loadDashboard()
    ]);
  } catch (error) {
    showMessage("Assignment failed: " + error.message, true);
  }
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#kbn5-ops-assign-button")) {
    assignDeliveryStaff();
  }

  if (event.target.closest("#kbn5-ops-load-staff")) {
    loadDeliveryStaff();
  }
});

window.KBN5OperationsUI.loadDeliveryStaff = loadDeliveryStaff;
window.KBN5OperationsUI.assignDeliveryStaff = assignDeliveryStaff;

/* Operations dashboard controls */

async function refreshOperations() {
  showMessage("Refreshing operations dashboard...");

  await Promise.allSettled([
    loadDashboard(),
    loadWarehouseOrders(),
    loadDeliveryOrders(),
    loadDeliveryStaff()
  ]);
}

function openOperations() {
  const panel = document.getElementById("kbn5-ops-panel");
  if (panel) {
    panel.hidden = false;
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  refreshOperations();
}

function closeOperations() {
  const panel = document.getElementById("kbn5-ops-panel");
  if (panel) panel.hidden = true;
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#kbn5-ops-toggle")) openOperations();
  if (event.target.closest("#kbn5-ops-close")) closeOperations();
  if (event.target.closest("#kbn5-ops-refresh")) refreshOperations();
});

window.KBN5OperationsUI.refresh = refreshOperations;
window.KBN5OperationsUI.open = openOperations;
window.KBN5OperationsUI.close = closeOperations;

document.addEventListener("DOMContentLoaded", () => {
  const panel = document.getElementById("kbn5-ops-panel");
  if (panel && !panel.hidden) refreshOperations();
});
