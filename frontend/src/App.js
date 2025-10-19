import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { getTracer } from './monitoring';
import ProductDetail from './ProductDetail';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const COUNTRIES = [
  { code: 'US', name: 'United States', flag: '🇺🇸' },
  { code: 'UK', name: 'United Kingdom', flag: '🇬🇧' },
  { code: 'DE', name: 'Germany', flag: '🇩🇪' },
  { code: 'FR', name: 'France', flag: '🇫🇷' },
  { code: 'JP', name: 'Japan', flag: '🇯🇵' },
  { code: 'BR', name: 'Brazil', flag: '🇧🇷' },
  { code: 'IN', name: 'India', flag: '🇮🇳' },
];

const AUTH_TOKEN = 'user-token-123';

function ProductList({
  products,
  loadingProducts,
  selectedCountry,
  COUNTRIES,
  isLoggedIn,
  loading,
  addToCart
}) {
  const navigate = useNavigate();

  return (
    <div className="products-section">
      <h2>
        Products for {COUNTRIES.find(c => c.code === selectedCountry)?.flag} {COUNTRIES.find(c => c.code === selectedCountry)?.name}
      </h2>
      {loadingProducts ? (
        <div className="loading-message">
          <p>⏳ Loading products for {COUNTRIES.find(c => c.code === selectedCountry)?.name}...</p>
        </div>
      ) : (
        <div className="products-grid">
          {products.map(product => (
            <div key={product.id} className="product-card">
              <div onClick={() => navigate(`/product/${product.id}`)} style={{ cursor: 'pointer' }}>
                <h3>{product.name}</h3>
                <p className="price">${product.price.toFixed(2)}</p>
                <p className="stock">
                  {product.stock > 0 ? `✅ ${product.stock} in stock` : '❌ Out of stock'}
                </p>
                <p className="category">{product.category}</p>
              </div>
              <button
                onClick={() => addToCart(product.id)}
                disabled={loading || product.stock === 0}
                className="btn btn-primary"
              >
                {product.stock === 0 ? '❌ Out of Stock' : '🛒 Add to Cart'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function App() {
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState([]);
  const [selectedCountry, setSelectedCountry] = useState('US');
  const [loading, setLoading] = useState(false);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [message, setMessage] = useState('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    fetchProducts();
  }, [selectedCountry]);

  const axiosConfig = {
    headers: {
      'Authorization': `Bearer ${AUTH_TOKEN}`
    }
  };

  const fetchProducts = async () => {
    setLoadingProducts(true);
    const tracer = getTracer();
    const span = tracer.startSpan('fetch_products', {
      attributes: {
        'user.country': selectedCountry,
      }
    });

    try {
      const response = await axios.get(`${API_URL}/${selectedCountry.toLowerCase()}/products`);
      setProducts(response.data);
      span.setAttribute('product.count', response.data.length);
      span.setStatus({ code: 1 }); // OK
    } catch (error) {
      console.error('Failed to fetch products:', error);
      span.recordException(error);
      span.setStatus({ code: 2, message: error.message }); // ERROR
      showMessage('Failed to load products', 'error');
    } finally {
      span.end();
      setLoadingProducts(false);
    }
  };

  const fetchCart = async () => {
    if (!isLoggedIn) return;

    try {
      const response = await axios.get(`${API_URL}/cart`, axiosConfig);
      setCart(response.data.items || []);
    } catch (error) {
      console.error('Failed to fetch cart:', error);
      const tracer = getTracer();
      const span = tracer.startSpan('fetch_cart_error');
      span.recordException(error);
      span.end();
    }
  };

  const handleLogin = () => {
    const tracer = getTracer();
    const span = tracer.startSpan('user_login', {
      attributes: {
        'user.country': selectedCountry,
      }
    });
    span.end();

    setIsLoggedIn(true);
    showMessage('Logged in successfully!', 'success');
    fetchCart();
  };

  const handleLogout = () => {
    const tracer = getTracer();
    const span = tracer.startSpan('user_logout');
    span.end();

    setIsLoggedIn(false);
    setCart([]);
    showMessage('Logged out successfully!', 'success');
  };

  const addToCart = async (productId) => {
    const tracer = getTracer();

    if (!isLoggedIn) {
      // Add to local cart if not logged in
      const product = products.find(p => p.id === productId);
      if (product) {
        const span = tracer.startSpan('add_to_cart_local', {
          attributes: {
            'product.id': productId,
            'product.name': product.name,
            'user.country': selectedCountry,
            'cart.type': 'local'
          }
        });

        const existingItem = cart.find(item => item.product_id === productId);
        if (existingItem) {
          setCart(cart.map(item =>
            item.product_id === productId
              ? { ...item, quantity: item.quantity + 1, subtotal: (item.quantity + 1) * product.price }
              : item
          ));
        } else {
          setCart([...cart, {
            id: Date.now(),
            product_id: productId,
            product_name: product.name,
            quantity: 1,
            price: product.price,
            subtotal: product.price
          }]);
        }
        showMessage(`Added ${product.name} to cart! Log in to checkout.`, 'success');
        span.end();
      }
      return;
    }

    setLoading(true);
    const span = tracer.startSpan('add_to_cart', {
      attributes: {
        'product.id': productId,
        'user.country': selectedCountry,
        'cart.type': 'server'
      }
    });

    try {
      const response = await axios.post(
        `${API_URL}/cart/add`,
        {
          product_id: productId,
          quantity: 1,
          country: selectedCountry
        },
        axiosConfig
      );

      span.setAttribute('product.name', response.data.product_name);
      span.setStatus({ code: 1 });
      showMessage(`Added ${response.data.product_name} to cart!`, 'success');
      await fetchCart();
    } catch (error) {
      console.error('Failed to add to cart:', error);
      span.recordException(error);
      span.setStatus({ code: 2, message: error.message });
      showMessage(error.response?.data?.detail || 'Failed to add to cart', 'error');
    } finally {
      span.end();
      setLoading(false);
    }
  };

  const checkout = async () => {
    if (!isLoggedIn) {
      showMessage('Please log in to checkout', 'error');
      return;
    }

    if (cart.length === 0) {
      showMessage('Cart is empty', 'error');
      return;
    }

    setLoading(true);
    const tracer = getTracer();
    const span = tracer.startSpan('checkout', {
      attributes: {
        'user.country': selectedCountry,
        'cart.size': cart.length,
        'payment.method': 'credit_card'
      }
    });

    try {
      const response = await axios.post(
        `${API_URL}/checkout`,
        {
          payment_method: 'credit_card',
          country: selectedCountry
        },
        axiosConfig
      );

      span.setAttribute('order.id', response.data.order_id);
      span.setAttribute('order.amount', response.data.total_amount);
      span.setStatus({ code: 1 });

      showMessage(
        `Checkout successful! Order ID: ${response.data.order_id}, Total: $${response.data.total_amount.toFixed(2)}`,
        'success'
      );
      setCart([]);
    } catch (error) {
      console.error('Checkout failed:', error);
      span.recordException(error);
      span.setStatus({ code: 2, message: error.message });
      showMessage(error.response?.data?.detail || 'Checkout failed', 'error');
    } finally {
      span.end();
      setLoading(false);
    }
  };

  const showMessage = (text, type) => {
    setMessage({ text, type });
    setTimeout(() => setMessage(''), 5000);
  };

  const cartTotal = cart.reduce((sum, item) => sum + item.subtotal, 0);

  return (
    <Router>
      <div className="App">
        <header className="header">
          <h1>🌍 Global WebStore</h1>
          <div className="header-controls">
            <div className="country-selector">
              <label>🗺️ Select Your Market: </label>
              <select
                value={selectedCountry}
                onChange={(e) => {
                  const newCountry = e.target.value;
                  const tracer = getTracer();
                  const span = tracer.startSpan('country_changed', {
                    attributes: {
                      'country.new': newCountry,
                      'country.previous': selectedCountry
                    }
                  });
                  span.end();

                  setSelectedCountry(newCountry);
                  showMessage(`Switched to ${COUNTRIES.find(c => c.code === newCountry)?.name} market`, 'success');
                }}
                className="country-select"
              >
                {COUNTRIES.map(country => (
                  <option key={country.code} value={country.code}>
                    {country.flag} {country.name}
                  </option>
                ))}
              </select>
              <span className="country-hint">Products and pricing vary by country</span>
            </div>
            <div className="auth-controls">
              {!isLoggedIn ? (
                <button onClick={handleLogin} className="btn btn-primary">
                  🔐 Login
                </button>
              ) : (
                <button onClick={handleLogout} className="btn btn-secondary">
                  👋 Logout
                </button>
              )}
            </div>
          </div>
        </header>

        {message && (
          <div className={`message ${message.type}`}>
            {message.text}
          </div>
        )}

        <div className="container">
          <Routes>
            <Route
              path="/"
              element={
                <>
                  <ProductList
                    products={products}
                    loadingProducts={loadingProducts}
                    selectedCountry={selectedCountry}
                    COUNTRIES={COUNTRIES}
                    isLoggedIn={isLoggedIn}
                    loading={loading}
                    addToCart={addToCart}
                  />
                  <div className="cart-section">
                    <h2>Shopping Cart</h2>
                    {cart.length === 0 ? (
                      <p className="cart-empty">Your cart is empty</p>
                    ) : (
                      <>
                        <div className="cart-items">
                          {cart.map(item => (
                            <div key={item.id} className="cart-item">
                              <div className="cart-item-details">
                                <strong>{item.product_name}</strong>
                                <span>Qty: {item.quantity}</span>
                              </div>
                              <div className="cart-item-price">
                                ${item.subtotal.toFixed(2)}
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="cart-total">
                          <strong>Total:</strong>
                          <strong>${cartTotal.toFixed(2)}</strong>
                        </div>
                        {!isLoggedIn && (
                          <p className="login-hint" style={{ textAlign: 'center', marginBottom: '10px', color: '#666' }}>
                            Please log in to checkout
                          </p>
                        )}
                        <button
                          onClick={checkout}
                          disabled={loading || !isLoggedIn}
                          className="btn btn-success btn-block"
                        >
                          {loading ? 'Processing...' : 'Checkout'}
                        </button>
                      </>
                    )}
                  </div>
                </>
              }
            />
            <Route
              path="/product/:productId"
              element={
                <ProductDetail
                  selectedCountry={selectedCountry}
                  isLoggedIn={isLoggedIn}
                  onAddToCart={addToCart}
                  showMessage={showMessage}
                />
              }
            />
          </Routes>
        </div>

        <footer className="footer">
          <p>Monitoring Demo - OpenTelemetry + Grafana Stack</p>
        </footer>
      </div>
    </Router>
  );
}

export default App;
