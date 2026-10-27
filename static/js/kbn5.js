const catalogue = [
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
          <button class="add-button" onclick="addToCart(${p.id})">
            ${cart[p.id] ? "Added +" : "+ Add"}
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

function changeQty(id, amount) {
  cart[id] = (cart[id] || 0) + amount;
  if (cart[id] <= 0) delete cart[id];
  renderProducts();
  renderCart();
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
  if (!Object.keys(cart).length) return;
  showToast("Demo only — no real order or payment placed");
}

el("search").addEventListener("input", renderProducts);

renderCategories();
renderProducts();
renderCart();
renderAdmin();
