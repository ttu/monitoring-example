import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { getTracer } from './monitoring';
import './ProductDetail.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const AUTH_TOKEN = 'user-token-123';

function ProductDetail({ selectedCountry, isLoggedIn, onAddToCart, showMessage }) {
  const { productId } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [addingToCart, setAddingToCart] = useState(false);

  useEffect(() => {
    fetchProductDetail();
  }, [productId, selectedCountry]);

  const axiosConfig = {
    headers: {
      'Authorization': `Bearer ${AUTH_TOKEN}`
    }
  };

  const fetchProductDetail = async () => {
    setLoading(true);
    const tracer = getTracer();
    const span = tracer.startSpan('view_product_detail', {
      attributes: {
        'product.id': productId,
        'user.country': selectedCountry
      }
    });

    try {
      const response = await axios.get(
        `${API_URL}/${selectedCountry.toLowerCase()}/products/${productId}`
      );
      setProduct(response.data);
      span.setAttribute('product.name', response.data.name);
      span.setAttribute('product.price', response.data.price);
      span.setAttribute('product.stock', response.data.stock);
      span.setStatus({ code: 1 });
    } catch (error) {
      console.error('Failed to fetch product:', error);
      span.recordException(error);
      span.setStatus({ code: 2, message: error.message });
      showMessage('Failed to load product details', 'error');
    } finally {
      span.end();
      setLoading(false);
    }
  };

  const handleAddToCart = async () => {
    setAddingToCart(true);
    try {
      await onAddToCart(product.id);
    } finally {
      setAddingToCart(false);
    }
  };

  if (loading) {
    return (
      <div className="product-detail">
        <div className="loading-message">
          <p>⏳ Loading product details...</p>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="product-detail">
        <div className="error-message">
          <p>Product not found</p>
          <button onClick={() => navigate('/')} className="btn btn-primary">
            ← Back to Products
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="product-detail">
      <button onClick={() => navigate('/')} className="btn btn-back">
        ← Back to Products
      </button>

      <div className="product-detail-card">
        <div className="product-detail-header">
          <h1>{product.name}</h1>
          <p className="product-category">{product.category}</p>
        </div>

        <div className="product-detail-content">
          <div className="product-detail-info">
            <div className="product-price">
              <span className="price-label">Price</span>
              <span className="price-value">${product.price.toFixed(2)}</span>
            </div>

            <div className="product-stock">
              <span className="stock-label">Availability</span>
              <span className={`stock-value ${product.stock > 0 ? 'in-stock' : 'out-of-stock'}`}>
                {product.stock > 0 ? `✅ ${product.stock} in stock` : '❌ Out of stock'}
              </span>
            </div>

            <div className="product-id">
              <span className="id-label">Product ID</span>
              <span className="id-value">#{product.id}</span>
            </div>
          </div>

          <div className="product-actions">
            <button
              onClick={handleAddToCart}
              disabled={addingToCart || product.stock === 0}
              className="btn btn-primary btn-large"
            >
              {product.stock === 0
                ? '❌ Out of Stock'
                : addingToCart
                  ? 'Adding...'
                  : '🛒 Add to Cart'}
            </button>
            {!isLoggedIn && (
              <p className="login-hint">Log in to checkout</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProductDetail;
