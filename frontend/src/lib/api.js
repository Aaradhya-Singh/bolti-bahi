const BASE_URL = "http://localhost:8000";

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${errorBody || res.statusText}`);
  }
  return res.json();
}

// ─── Voice ───────────────────────────────────────────────────────────
export async function processVoice(audioBlob, shopId, languageCode) {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");
  formData.append("shop_id", shopId);
  formData.append("language_code", languageCode);

  const res = await fetch(`${BASE_URL}/api/voice/process`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "");
    throw new Error(`Voice API error ${res.status}: ${errorBody || res.statusText}`);
  }
  return res.json();
}

// ─── Dashboard ───────────────────────────────────────────────────────
export async function getDashboard(shopId) {
  return request(`/api/shops/${shopId}/dashboard`);
}

// ─── Customers ───────────────────────────────────────────────────────
export async function getCustomers(shopId, search) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  const query = params.toString();
  return request(`/api/shops/${shopId}/customers${query ? `?${query}` : ""}`);
}

export async function getCustomerDetail(shopId, customerId) {
  return request(`/api/shops/${shopId}/customers/${customerId}`);
}

export async function getCustomerTransactions(shopId, customerId) {
  return request(`/api/shops/${shopId}/customers/${customerId}/transactions`);
}

export async function addCustomer(shopId, data) {
  return request(`/api/shops/${shopId}/customers`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ─── Transactions ────────────────────────────────────────────────────
export async function getTransactions(shopId, filters) {
  const params = new URLSearchParams();
  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        params.set(key, value);
      }
    });
  }
  const query = params.toString();
  return request(`/api/shops/${shopId}/transactions${query ? `?${query}` : ""}`);
}

export async function addTransaction(shopId, data) {
  return request(`/api/shops/${shopId}/transactions`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ─── Products / Inventory ────────────────────────────────────────────
export async function getProducts(shopId, lowStock) {
  const params = new URLSearchParams();
  if (lowStock) params.set("low_stock", "true");
  const query = params.toString();
  return request(`/api/shops/${shopId}/products${query ? `?${query}` : ""}`);
}

export async function addProduct(shopId, data) {
  return request(`/api/shops/${shopId}/products`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateStock(shopId, productId, data) {
  return request(`/api/shops/${shopId}/products/${productId}/stock`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ─── Shop ────────────────────────────────────────────────────────────
export async function createShop(data) {
  return request("/api/shops", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
