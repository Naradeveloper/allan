// -------------------- PRODUCT DATA --------------------
const products = [
  { id: 1, name: "Ashwagandha Root", price: 550, category: "herbal-roots", image: "c:\Users\HP EliteBook 755 G5\Downloads\alans web.png.jpg" },
  { id: 2, name: "Mukombero", price: 400, category: "herbal-roots", image: "images/mukombero.jpg" },
  { id: 3, name: "Onion Powder", price: 120, category: "powders", image: "images/onion_powder.jpg" },
  { id: 4, name: "Turmeric Powder", price: 180, category: "powders", image: "images/turmeric_powder.jpg" },
  { id: 5, name: "Cinnamon Sticks", price: 250, category: "dried-herbs", image: "images/cinnamon.jpg" },
  { id: 6, name: "Clove Buds", price: 300, category: "dried-herbs", image: "images/clove.jpg" },
  { id: 7, name: "Ginger Powder", price: 200, category: "powders", image: "images/ginger.jpg" },
  { id: 8, name: "Lemongrass Tea", price: 350, category: "teas", image: "images/lemongrass.jpg" },
  { id: 9, name: "Chamomile Tea", price: 400, category: "teas", image: "images/chamomile.jpg" },
  { id: 10, name: "Moringa Leaves", price: 220, category: "dried-herbs", image: "images/moringa.jpg" },
  { id: 11, name: "Curry Powder", price: 260, category: "seasoning", image: "images/curry.jpg" },
  { id: 12, name: "Paprika", price: 190, category: "powders", image: "images/paprika.jpg" },
  { id: 13, name: "Detox Blend", price: 480, category: "wellness-blends", image: "images/detox.jpg" },
  { id: 14, name: "Immunity Mix", price: 500, category: "wellness-blends", image: "images/immunity.jpg" },
  { id: 15, name: "Relaxation Tea", price: 430, category: "teas", image: "images/relaxation.jpg" }
];
let cart = [];
const productGrid = document.getElementById("productGrid");
const cartBtn = document.getElementById("cartBtn");
const cartModal = document.getElementById("cartModal");
const overlay = document.getElementById("overlay");
const cartItems = document.getElementById("cartItems");
const cartSummary = document.getElementById("cartSummary");

// -------------------- DISPLAY PRODUCTS --------------------
function displayProducts(filter = "all") {
  productGrid.innerHTML = "";
  const filtered = filter === "all" ? products : products.filter(p => p.category === filter);

  filtered.forEach(p => {
    const productCard = document.createElement("div");
    productCard.className = "product-card";
    productCard.innerHTML = `
      <img src="${p.image}" alt="${p.name}">
      <h4>${p.name}</h4>
      <p>KSh ${p.price}</p>
      <label>Qty: <input type="number" value="1" min="1" id="qty-${p.id}" class="qty-input"></label>
      <button class="addCartBtn" data-id="${p.id}">Add to Cart</button>
    `;
    productGrid.appendChild(productCard);
  });
}
displayProducts();

// -------------------- FILTER BUTTONS --------------------
document.querySelectorAll(".filterBtn, .nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const category = btn.dataset.cat || btn.dataset.filter;
    displayProducts(category);
  });
});

// -------------------- ADD TO CART --------------------
document.addEventListener("click", e => {
  if (e.target.classList.contains("addCartBtn")) {
    const id = parseInt(e.target.dataset.id);
    const qtyInput = document.getElementById(`qty-${id}`);
    const qty = parseInt(qtyInput.value);
    const product = products.find(p => p.id === id);
    const existing = cart.find(i => i.id === id);

    if (existing) existing.qty += qty;
    else cart.push({ ...product, qty });

    updateCartDisplay();
  }
});

function updateCartDisplay() {
  cartBtn.innerText = `🛒 Cart (${cart.length})`;
}

// -------------------- CART MODAL --------------------
cartBtn.addEventListener("click", () => {
  overlay.hidden = false;
  cartModal.setAttribute("aria-hidden", "false");
  renderCart();
});

document.getElementById("closeCart").addEventListener("click", closeModals);

function renderCart() {
  cartItems.innerHTML = "";
  let total = 0;
  cart.forEach(item => {
    total += item.price * item.qty;
    cartItems.innerHTML += `
      <div class="cart-item">
        <p>${item.name} (${item.qty}) - KSh ${item.price * item.qty}</p>
        <button class="minus" data-id="${item.id}">-</button>
        <button class="plus" data-id="${item.id}">+</button>
        <button class="remove" data-id="${item.id}">Remove</button>
      </div>
    `;
  });
  cartSummary.innerHTML = `<h4>Total: KSh ${total}</h4>`;
}

// Adjust quantity buttons
document.addEventListener("click", e => {
  const id = parseInt(e.target.dataset.id);
  if (e.target.classList.contains("minus")) {
    const item = cart.find(i => i.id === id);
    if (item && item.qty > 1) item.qty--;
    renderCart();
  } else if (e.target.classList.contains("plus")) {
    const item = cart.find(i => i.id === id);
    if (item) item.qty++;
    renderCart();
  } else if (e.target.classList.contains("remove")) {
    cart = cart.filter(i => i.id !== id);
    updateCartDisplay();
    renderCart();
  }
});

// -------------------- MPESA PAYMENT (Simulation) --------------------
document.getElementById("mpesaPayBtn").addEventListener("click", () => {
  const phone = prompt("Enter your M-Pesa phone number (2547...)");
  if (phone) alert("M-Pesa payment request sent to " + phone + ". Thank you!");
  closeModals();
});

// -------------------- CUSTOMER PANEL BUTTONS --------------------
document.getElementById("sellBtn").addEventListener("click", () => openModal("sellerModal"));
document.getElementById("profileBtn").addEventListener("click", () => openModal("profileModal"));
document.getElementById("myOrdersBtn").addEventListener("click", () => openModal("ordersModal"));
document.getElementById("wishlistBtn").addEventListener("click", () => alert("Wishlist feature coming soon!"));
document.getElementById("feedbackBtn").addEventListener("click", () => alert("Thank you for your feedback! Feature under development."));
document.getElementById("viewProducts").addEventListener("click", () => displayProducts());

// -------------------- REGISTER / LOGIN --------------------
document.getElementById("registerBtn").addEventListener("click", () => openModal("registerModal"));
document.getElementById("loginBtn").addEventListener("click", () => openModal("loginModal"));

document.getElementById("registerForm").addEventListener("submit", e => {
  e.preventDefault();
  alert("Registration successful!");
  closeModals();
});

document.getElementById("loginForm").addEventListener("submit", e => {
  e.preventDefault();
  alert("Login successful!");
  closeModals();
});

// -------------------- SELLER FORM --------------------
document.getElementById("sellerForm").addEventListener("submit", e => {
  e.preventDefault();
  alert("Your product has been submitted to ALIMAQ for review!");
  closeModals();
});

// -------------------- THEME TOGGLE --------------------
document.getElementById("themeBtn").addEventListener("click", () => {
  document.body.classList.toggle("dark-theme");
});

// -------------------- MODALS --------------------
function openModal(id) {
  overlay.hidden = false;
  document.getElementById(id).setAttribute("aria-hidden", "false");
}
function closeModals() {
  overlay.hidden = true;
  document.querySelectorAll(".modal").forEach(m => m.setAttribute("aria-hidden", "true"));
}
document.querySelectorAll("[data-close]").forEach(btn => btn.addEventListener("click", closeModals));
