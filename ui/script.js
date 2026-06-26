const API_BASE = "https://codevector-4sko.onrender.com";

const productsContainer = document.getElementById("products");
const categorySelect = document.getElementById("categorySelect");
const loadMoreButton = document.getElementById("loadMoreButton");
const refreshButton = document.getElementById("refreshButton");
const simulateButton = document.getElementById("simulateButton");
const statusText = document.getElementById("status");
const duplicateAlert = document.getElementById("duplicateAlert");

let cursor = null;
let hasMore = true;
let loading = false;

// Track every product ID we have shown the user.
// If an ID appears twice, cursor pagination has failed.
const seenIds = new Set();

// ─── Categories ────────────────────────────────────────────

async function loadCategories() {
    try {
        const res = await fetch(`${API_BASE}/categories`);
        const data = await res.json();

        (data.categories || data).forEach((cat) => {
            const opt = document.createElement("option");
            opt.value = cat;
            opt.textContent = cat;
            categorySelect.appendChild(opt);
        });
    } catch (err) {
        console.error("loadCategories:", err);
    }
}

// ─── Products ──────────────────────────────────────────────

async function loadProducts(reset = false) {
    if (loading) return;
    loading = true;
    statusText.textContent = "Loading...";

    try {
        let url = `${API_BASE}/products?limit=20`;

        if (categorySelect.value) {
            url += `&category=${encodeURIComponent(categorySelect.value)}`;
        }

        if (!reset && cursor) {
            url += `&cursor=${encodeURIComponent(cursor)}`;
        }

        const res = await fetch(url);
        const data = await res.json();

        if (reset) {
            // Fresh start — clear everything including duplicate tracking.
            productsContainer.innerHTML = "";
            seenIds.clear();
            duplicateAlert.style.display = "none";
        }

        data.products.forEach((product) => {
            const isDuplicate = seenIds.has(product.id);

            if (isDuplicate) {
                // This should NEVER happen with correct cursor pagination.
                // If it does, the card is highlighted in red.
                duplicateAlert.style.display = "block";
                duplicateAlert.textContent =
                    `Duplicate detected! Product ID ${product.id} appeared twice. Pagination is broken.`;
            }

            seenIds.add(product.id);

            const card = document.createElement("div");
            card.className = isDuplicate ? "card card--duplicate" : "card";

            card.innerHTML = `
                <h3>${product.name}</h3>
                <div class="category">${product.category}</div>
                <div class="price">$${Number(product.price).toFixed(2)}</div>
                <div class="meta">ID: ${product.id}</div>
                <div class="meta">Created: ${new Date(product.created_at).toLocaleString()}</div>
            `;

            productsContainer.appendChild(card);
        });

        cursor = data.next_cursor;
        hasMore = data.has_more;

        loadMoreButton.style.display = hasMore ? "block" : "none";
        statusText.textContent = `${seenIds.size} unique products loaded — no duplicates detected`;

    } catch (err) {
        console.error("loadProducts:", err);
        statusText.textContent = "Failed to load products.";
    }

    loading = false;
}

// ─── Simulate Updates ──────────────────────────────────────

async function simulateUpdates() {
    simulateButton.disabled = true;
    simulateButton.textContent = "Inserting...";

    try {
        const res = await fetch(`${API_BASE}/products/simulate-updates`, { method: "POST" });
        const data = await res.json();

        // Show a temporary notice — does NOT reset the page or cursor.
        // The user can keep clicking "Load More" and should see no duplicates.
        statusText.textContent =
            `${data.inserted} new products added at the top of the list. `
            + `Keep clicking "Load More" — your cursor is unaffected.`;

    } catch (err) {
        console.error("simulateUpdates:", err);
        statusText.textContent = "Simulate failed.";
    }

    simulateButton.disabled = false;
    simulateButton.textContent = "Simulate 50 Updates";
}

// ─── Event Listeners ───────────────────────────────────────

categorySelect.addEventListener("change", () => {
    cursor = null;
    hasMore = true;
    loadProducts(true);
});

refreshButton.addEventListener("click", () => {
    cursor = null;
    hasMore = true;
    loadProducts(true);
});

loadMoreButton.addEventListener("click", () => {
    if (hasMore) loadProducts(false);
});

simulateButton.addEventListener("click", simulateUpdates);

// ─── Boot ──────────────────────────────────────────────────

loadCategories();
loadProducts(true);