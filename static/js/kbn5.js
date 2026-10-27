let catalogue = [
  {id:1,name:"Fresh Tomatoes",category:"Vegetables",price:30,unit:"500 g",emoji:"🍅",color:"#fce8df",tag:"FRESH"},
  {id:2,name:"Green Vegetables",category:"Vegetables",price:40,unit:"bunch",emoji:"🥬",color:"#e4f0d9",tag:"LOCAL PICK"},
  {id:3,name:"Fresh Apples",category:"Fruits",price:120,unit:"500 g",emoji:"🍎",color:"#f8e5df",tag:"POPULAR"},
  {id:4,name:"Bananas",category:"Fruits",price:50,unit:"dozen",emoji:"🍌",color:"#f8efc9",tag:"VALUE"},
  {id:5,name:"Fresh Milk",category:"Dairy",price:32,unit:"500 ml",emoji:"🥛",color:"#e4eff8",tag:"DAILY ESSENTIAL"},
  {id:6,name:"Bread",category:"Bakery",price:35,unit:"pack",emoji:"🍞",color:"#f3e7d4",tag:"FRESH"},
  {id:7,name:"Potato Chips",category:"Snacks",price:20,unit:"pack",emoji:"🍟",color:"#f7e8cc",tag:"SNACK TIME"},
  {id:8,name:"Packaged Water",category:"Drinks",price:20,unit:"1 litre",emoji:"💧",color:"#dff1f7",tag:"EVERYDAY"}
];

let activeCategory = "All";
let cart = {};
let toastTimer;

const money = value => "₹" + value.toLocaleString("en-IN");
const el = id => document.getElementById(id);

function renderCategories() {
  const categories = ["All", ...new Set(catalogue.map(p => p.category))];
  el("categories").innerHTML = categories.map(category => `
    <button class="category ${category === activeCategory ? "active" : ""}"
      onclick="selectCategory('${category}')">${category}</button>
  `).join("");
}

function renderProducts() {
  const query = el("search").value.trim().toLowerCase();

  const products = catalogue.filter(p =>
    (activeCategory === "All" || p.category === activeCategory) &&
    (p.name.toLowerCase().includes(query) ||
     p.category.toLowerCase().includes(query))
  );

  el("result-title").textContent =
    activeCategory === "All" ? "Popular picks" : activeCategory;

  el("result-count").textContent =
    `${products.length} product${products.length === 1 ? "" : "s"}`;

  el("empty").hidden = products.length > 0;

  el("products").innerHTML = products.map(p => `
    <article class="product-card">
      <div class="product-visual" style="background:${p.color}">
        <span class="product-label">${p.tag}</span>
        <span class="product-emoji">${p.emoji}</span>
      </div>
      <div class="product-info">
        <h3>${p.name}</h3>
        <p>${p.unit} · ${p.category}</p>
        <div class="product-bottom">
          <span class="price">${money(p.price)}</span>
          <button class="add-button"
            onclick="addToCart(${p.id})"
            ${p.stock !== undefined && Number(p.stock) <= 0 ? "disabled" : ""}>
            ${p.stock !== undefined && Number(p.stock) <= 0
              ? "Out of stock"
              : cart[p.id] ? "Added +" : "+ Add"}
          </button>
        </div>
      </div>
    </article>
  `).join("");
}

function selectCategory(category) {
  activeCategory = category;
  renderCategories();
  renderProducts();
}

function addToCart(id) {
  cart[id] = (cart[id] || 0) + 1;
  renderProducts();
  renderCart();
  showToast("Added to your bag");
}

async function changeQty(id, amount) {
  if (!accountToken || !accountUser) {
    openAccount();
    showToast("Please sign in to update your cart");
    return;
  }

  try {
    const currentQty = Number(cart[id] || 0);
    const nextQty = currentQty + amount;

    const data = await kbn5Api("/api/v1/cart/");
    const item = (data.items || []).find(
      row => Number(row.product_id) === Number(id)
    );

    if (!item) {
      if (nextQty > 0) {
        await kbn5Api("/api/v1/cart/items", {
          method: "POST",
          body: JSON.stringify({
            product_id: Number(id),
            quantity: nextQty
          })
        });
      }
    } else if (nextQty <= 0) {
      await kbn5Api(`/api/v1/cart/items/${item.id}`, {
        method: "DELETE"
      });
    } else {
      await kbn5Api(`/api/v1/cart/items/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({quantity: nextQty})
      });
    }

    await refreshServerCart();
  } catch (error) {
    showToast(error.message || "Could not update cart");
  }
}

function renderCart() {
  const entries = catalogue.filter(p => cart[p.id]);
  const count = Object.values(cart).reduce((a, b) => a + b, 0);
  const total = entries.reduce((sum, p) => sum + p.price * cart[p.id], 0);

  el("cart-count").textContent = count;
  el("cart-empty").hidden = entries.length > 0;
  el("cart-summary").hidden = entries.length === 0;

  el("cart-items").innerHTML = entries.map(p => `
    <div class="cart-row">
      <span class="cart-emoji">${p.emoji}</span>
      <div class="cart-detail">
        <b>${p.name}</b>
        <small>${money(p.price)} · ${p.unit}</small>
      </div>
      <div class="qty">
        <button onclick="changeQty(${p.id},-1)" aria-label="Decrease">−</button>
        <b>${cart[p.id]}</b>
        <button onclick="changeQty(${p.id},1)" aria-label="Increase">+</button>
      </div>
    </div>
  `).join("");

  el("cart-subtotal").textContent = "Subtotal: " + money(total);
}

function openCart() {
  el("cart-overlay").classList.add("open");
}

function closeCart() {
  el("cart-overlay").classList.remove("open");
}

function showAdmin() {
  el("store-view").hidden = true;
  el("admin-view").hidden = false;
  renderAdmin();
  window.scrollTo(0, 0);
}

function showStore() {
  el("admin-view").hidden = true;
  el("store-view").hidden = false;
  window.scrollTo(0, 0);
}

function renderAdmin() {
  el("admin-product-count").textContent = catalogue.length;
  el("admin-products").innerHTML = catalogue.map(p => `
    <div class="admin-product">
      <span>${p.emoji}</span>
      <b>${p.name}</b>
      <small>${p.category}</small>
      <strong>${money(p.price)} / ${p.unit}</strong>
    </div>
  `).join("");
}

function showToast(message) {
  const toast = el("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
}

function checkoutDemo() {
  if (!accountToken || !accountUser) {
    showToast("Please sign in before checkout");
    openAccount();
    return;
  }

  if (!Object.values(cart).some(qty => Number(qty) > 0)) {
    showToast("Your cart is empty");
    return;
  }

  closeCart();
  el("checkout-message").textContent = "";
  el("checkout-overlay").classList.add("open");
}

el("search").addEventListener("input", renderProducts);

renderCategories();
renderProducts();
renderCart();
renderAdmin();


async function loadLiveProducts() {
  try {
    const response = await fetch("/api/v1/products/?per_page=50");
    if (!response.ok) throw new Error("Product API unavailable");

    const data = await response.json();

    catalogue = (data.items || []).map(p => {
      const category = p.category_name || "Essentials";
      const name = p.name || "Product";
      const text = (name + " " + category).toLowerCase();

      let emoji = "🛍️";
      if (/vegetable|tomato|potato|onion|spinach/.test(text)) emoji = "🥬";
      else if (/fruit|apple|banana|mango/.test(text)) emoji = "🍎";
      else if (/milk|dairy|cheese|curd/.test(text)) emoji = "🥛";
      else if (/bread|bakery|cake/.test(text)) emoji = "🍞";
      else if (/drink|water|juice/.test(text)) emoji = "🥤";
      else if (/snack|chip|biscuit/.test(text)) emoji = "🍪";

      return {
        id: p.id,
        name,
        category,
        price: Number(((Number(p.price_paise) || 0) / 100).toFixed(2)),
        unit: p.description || "Everyday essential",
        emoji,
        color: "#eaf1df",
        tag: Number(p.stock_quantity) > 0 ? "IN STOCK" : "OUT OF STOCK",
        stock: Number(p.stock_quantity) || 0
      };
    });

    // Remove cart entries for products no longer in the live catalogue.
    for (const id of Object.keys(cart)) {
      if (!catalogue.some(p => p.id === Number(id))) delete cart[id];
    }

    renderCategories();
    renderProducts();
    renderCart();
    renderAdmin();
    el("result-title").textContent = "Live catalogue";
  } catch (error) {
    el("result-title").textContent = "Demo catalogue · API unavailable";
    showToast("Live products unavailable; showing demo items");
  }
}

loadLiveProducts();

// KBN5 customer account: API-backed login and registration.
let accountMode = "login";
let accountToken = sessionStorage.getItem("kbn5_access_token") || "";
let accountUser = null;

function openAccount() {
  el("account-overlay").classList.add("open");
  updateAccountUI();
}

function closeAccount() {
  el("account-overlay").classList.remove("open");
}

function toggleAccountMode() {
  accountMode = accountMode === "login" ? "register" : "login";
  updateAccountUI();
}

function updateAccountUI() {
  const loggedIn = Boolean(accountToken && accountUser);

  el("account-title").textContent = loggedIn
    ? `Hello, ${accountUser.display_name || accountUser.username}`
    : accountMode === "login" ? "Welcome to KBN5" : "Create your account";

  el("account-form").hidden = loggedIn;
  el("account-mode").hidden = loggedIn;
  el("account-logout").hidden = !loggedIn;
  el("display-name-wrap").hidden = accountMode !== "register";
  el("email-wrap").hidden = accountMode !== "register";
  el("account-identity").placeholder = accountMode === "login"
    ? "Username or email" : "Choose a username";
  el("account-password").autocomplete = accountMode === "login"
    ? "current-password" : "new-password";
  el("account-submit").textContent = accountMode === "login"
    ? "Sign in" : "Create account";
  el("account-mode").textContent = accountMode === "login"
    ? "Create an account" : "Already registered? Sign in";
  el("account-button").textContent = loggedIn
    ? (accountUser.display_name || accountUser.username) : "Sign in";
}

async function accountRequest(path, payload) {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  const headers = {"Content-Type": "application/json"};
  if (csrf) headers["X-CSRFToken"] = csrf;
  if (accountToken) headers.Authorization = `Bearer ${accountToken}`;

  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers,
    body: JSON.stringify(payload)
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || data.message || "Request failed");
  return data;
}

el("account-form").addEventListener("submit", async event => {
  event.preventDefault();
  const submit = el("account-submit");
  const message = el("account-message");
  submit.disabled = true;
  message.textContent = "Please wait...";

  try {
    let data;
    if (accountMode === "register") {
      const username = el("account-identity").value.trim().toLowerCase();
      const email = el("account-email").value.trim().toLowerCase();
      const password = el("account-password").value;
      const display_name = el("account-display-name").value.trim() || username;

      data = await accountRequest("/api/v1/auth/register", {
        username, email, password, display_name
      });
    } else {
      data = await accountRequest("/api/v1/auth/login", {
        identity: el("account-identity").value.trim(),
        password: el("account-password").value
      });
    }

    accountToken = data.access_token || "";
    if (accountToken) {
      sessionStorage.setItem("kbn5_access_token", accountToken);
    }
    accountUser = data.user;
    message.textContent = data.message || "Signed in successfully.";
    updateAccountUI();
    showToast("Welcome to KBN5");
    await loadLiveProducts();
  } catch (error) {
    message.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

async function logoutAccount() {
  try {
    await accountRequest("/api/v1/auth/logout", {});
  } catch (error) {
    // Clear local account state even if the server session has expired.
  }

  accountToken = "";
  sessionStorage.removeItem("kbn5_access_token");
  accountUser = null;
  el("account-message").textContent = "You have signed out.";
  updateAccountUI();
  renderCart();
}

updateAccountUI();


// Shared authenticated API helper for cart, addresses and orders.
async function kbn5Api(path, options = {}) {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  const headers = {...(options.headers || {})};

  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (csrf) headers["X-CSRFToken"] = csrf;
  if (accountToken) headers.Authorization = `Bearer ${accountToken}`;

  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "same-origin"
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || data.message || `Request failed (${response.status})`);
  }
  return data;
}

// Load the authenticated customer's cart from the backend.
async function refreshServerCart() {
  const data = await kbn5Api("/api/v1/cart/");
  cart = {};

  for (const item of (data.items || [])) {
    cart[item.product_id] = Number(item.quantity) || 0;
  }

  renderCart();
}

// Replace the demo add-to-cart action with the real cart API.
if (typeof addToCart === "function") {
  const kbn5OriginalAddToCart = addToCart;

  addToCart = async function(productId) {
    const selectedProduct = catalogue.find(
      product => Number(product.id) === Number(productId)
    );

    if (!selectedProduct) {
      showToast("Product is no longer available");
      return;
    }

    if (selectedProduct.stock !== undefined &&
        Number(selectedProduct.stock) <= 0) {
      showToast("This product is out of stock");
      return;
    }

    if (!accountToken || !accountUser) {
      showToast("Please sign in before adding items");
      openAccount();
      return;
    }

    try {
      await kbn5Api("/api/v1/cart/items", {
        method: "POST",
        body: JSON.stringify({
          product_id: Number(productId),
          quantity: 1
        })
      });

      await refreshServerCart();
      showToast("Added to your server cart");
    } catch (error) {
      showToast(error.message || "Could not add this item");
    }
  };
}

// Restore the signed-in customer and cart after a page refresh.
async function restoreKbn5Account() {
  if (!accountToken) return;

  try {
    const data = await kbn5Api("/api/v1/auth/me");
    accountUser = data.user;
    updateAccountUI();
    await refreshServerCart();
  } catch (error) {
    accountToken = "";
    accountUser = null;
    sessionStorage.removeItem("kbn5_access_token");
    updateAccountUI();
  }
}

restoreKbn5Account();


// Save delivery address, then submit the order to the backend.
el("checkout-form").addEventListener("submit", async event => {
  event.preventDefault();

  const button = el("place-order-button");
  const message = el("checkout-message");

  if (!accountToken || !accountUser) {
    message.textContent = "Please sign in first.";
    openAccount();
    return;
  }

  button.disabled = true;
  message.textContent = "Saving address and placing order...";

  try {
    const addressPayload = {
      recipient_name: el("delivery-name").value.trim(),
      phone: el("delivery-phone").value.trim(),
      address_line: el("delivery-line").value.trim(),
      area_name: el("delivery-area").value.trim(),
      pincode: el("delivery-pincode").value.trim(),
      landmark: el("delivery-landmark").value.trim()
    };

    const existing = await kbn5Api("/api/v1/addresses/");
    const addresses = existing.items || [];

    let savedAddress = addresses.find(a =>
      a.recipient_name === addressPayload.recipient_name &&
      a.phone === addressPayload.phone &&
      a.address_line === addressPayload.address_line &&
      a.area_name === addressPayload.area_name &&
      a.pincode === addressPayload.pincode &&
      (a.landmark || "") === addressPayload.landmark
    );

    if (!savedAddress) {
      const created = await kbn5Api("/api/v1/addresses/", {
        method: "POST",
        body: JSON.stringify({
          ...addressPayload,
          label: "Home",
          is_default: addresses.length === 0
        })
      });
      savedAddress = created.address;
    }

    const addressId = savedAddress && savedAddress.id;

    if (!addressId) {
      throw new Error("Address saved, but its ID was not returned. Please check your account addresses before retrying.");
    }

    const result = await kbn5Api("/api/v1/orders/checkout", {
      method: "POST",
      body: JSON.stringify({address_id: addressId})
    });

    const order = result.order || {};
    message.textContent = `Order ${order.order_number || "#" + (order.id || "")} created. Payment is ${order.payment_status || "pending"}.`;
    showToast("Order request successful");
    await refreshServerCart();
  } catch (error) {
    message.textContent = error.message || "Checkout failed. Please review your details and try again.";
  } finally {
    button.disabled = false;
  }
});

function closeCheckout() {
  el("checkout-overlay").classList.remove("open");
}

// Customer order history.
function openOrders() {
  if (!accountToken || !accountUser) {
    showToast("Please sign in to view your orders");
    openAccount();
    return;
  }

  el("orders-overlay").classList.add("open");
  loadMyOrders();
}

function closeOrders() {
  el("orders-overlay").classList.remove("open");
}

async function loadMyOrders() {
  const list = el("orders-list");
  list.replaceChildren();

  const loading = document.createElement("p");
  loading.textContent = "Loading your orders...";
  list.appendChild(loading);

  if (!accountToken || !accountUser) {
    loading.textContent = "Please sign in to view your orders.";
    return;
  }

  try {
    const data = await kbn5Api("/api/v1/orders/");
    const orders = Array.isArray(data)
      ? data
      : (data.orders || data.items || []);

    list.replaceChildren();

    if (!orders.length) {
      const empty = document.createElement("p");
      empty.textContent = "No orders found yet.";
      list.appendChild(empty);
      return;
    }

    for (const order of orders) {
      const card = document.createElement("section");
      card.className = "order-card";

      const heading = document.createElement("h3");
      heading.textContent = `Order ${order.order_number || "#" + order.id}`;

      const status = document.createElement("p");
      status.textContent = `Status: ${order.status || "Processing"}`;

      const payment = document.createElement("p");
      payment.textContent = `Payment: ${order.payment_status || "Pending"}`;

      const total = document.createElement("p");
      const paise = Number(order.total_paise);
      total.textContent = Number.isFinite(paise)
        ? `Total: ₹${(paise / 100).toFixed(2)}`
        : "Total: Not available";

      card.append(heading, status, payment, total);
      list.appendChild(card);
    }
  } catch (error) {
    list.replaceChildren();
    const failed = document.createElement("p");
    failed.textContent = error.message || "Could not load orders. Please try again.";
    list.appendChild(failed);
  }
}
