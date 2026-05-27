# Lecture 4 — Practical Hands-On: Building Micro-frontends

> **Theory file:** [04_Micro_Frontends_UI_Composition.md](04_Micro_Frontends_UI_Composition.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

A **complete micro-frontend system** with:

1. ✅ **Shell application** (host) using Webpack Module Federation
2. ✅ **3 Remote MFEs** (Catalog, Cart, Profile) — independently built
3. ✅ **Shared design system** as npm package
4. ✅ **Cross-MFE event bus** for communication
5. ✅ **Routing strategies** (shell-based + independent)
6. ✅ **Independent CI/CD** per MFE
7. ✅ **Docker setup** for local development
8. ✅ **Error boundaries** for fault isolation
9. ✅ **Single-SPA alternative** demo

By end: aap **production micro-frontend system** bana sakte ho.

---

## 1. Project Structure

```
microfrontend-demo/
├── package.json
├── docker-compose.yml
├── README.md
│
├── shell/                          # Host application
│   ├── webpack.config.js
│   ├── package.json
│   └── src/
│       ├── App.tsx
│       ├── index.tsx
│       └── bootstrap.tsx
│
├── mfes/                           # Remote micro-frontends
│   ├── catalog/                    # Team A
│   │   ├── webpack.config.js
│   │   ├── package.json
│   │   └── src/
│   │       ├── CatalogPage.tsx
│   │       └── bootstrap.tsx
│   │
│   ├── cart/                       # Team B
│   │   ├── webpack.config.js
│   │   ├── package.json
│   │   └── src/
│   │       ├── CartPage.tsx
│   │       └── bootstrap.tsx
│   │
│   └── profile/                    # Team C
│       ├── webpack.config.js
│       ├── package.json
│       └── src/
│           ├── ProfilePage.tsx
│           └── bootstrap.tsx
│
├── shared/
│   └── design-system/              # Versioned design system
│       ├── package.json
│       ├── src/
│       │   ├── Button.tsx
│       │   ├── Card.tsx
│       │   └── tokens.css
│       └── stories/                 # Storybook
│
└── .github/
    └── workflows/
        ├── shell-ci.yml
        ├── catalog-ci.yml
        ├── cart-ci.yml
        └── profile-ci.yml
```

---

## 2. Setup & Dependencies

```bash
# Each MFE has its own package.json and node_modules
cd shell && npm install
cd ../mfes/catalog && npm install
cd ../cart && npm install
cd ../profile && npm install
```

### Common Dependencies (per MFE)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "@company/design-system": "^1.0.0"
  },
  "devDependencies": {
    "webpack": "^5.89.0",
    "webpack-cli": "^5.1.4",
    "webpack-dev-server": "^4.15.1",
    "@babel/core": "^7.23.0",
    "@babel/preset-env": "^7.23.0",
    "@babel/preset-react": "^7.23.0",
    "@babel/preset-typescript": "^7.23.0",
    "babel-loader": "^9.1.3",
    "html-webpack-plugin": "^5.5.4",
    "typescript": "^5.3.0"
  }
}
```

---

## 3. 🏠 Shell Application (Host)

### `shell/webpack.config.js`

```javascript
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { ModuleFederationPlugin } = require('webpack').container;
const path = require('path');

module.exports = {
    entry: './src/index.tsx',
    mode: 'development',
    devServer: {
        port: 3000,
        historyApiFallback: true,
        hot: true,
    },
    output: {
        publicPath: 'http://localhost:3000/',
        clean: true,
    },
    resolve: {
        extensions: ['.tsx', '.ts', '.jsx', '.js'],
    },
    module: {
        rules: [
            {
                test: /\.[jt]sx?$/,
                exclude: /node_modules/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['@babel/preset-env', '@babel/preset-react', '@babel/preset-typescript'],
                    },
                },
            },
            {
                test: /\.css$/,
                use: ['style-loader', 'css-loader'],
            },
        ],
    },
    plugins: [
        new ModuleFederationPlugin({
            name: 'shell',
            remotes: {
                // Each remote is loaded from its own URL at runtime
                catalog: 'catalog@http://localhost:3001/remoteEntry.js',
                cart: 'cart@http://localhost:3002/remoteEntry.js',
                profile: 'profile@http://localhost:3003/remoteEntry.js',
            },
            shared: {
                // Shared singletons — no duplicate React!
                react: {
                    singleton: true,
                    requiredVersion: '^18.2.0',
                    eager: false,
                },
                'react-dom': {
                    singleton: true,
                    requiredVersion: '^18.2.0',
                    eager: false,
                },
                'react-router-dom': {
                    singleton: true,
                    requiredVersion: '^6.20.0',
                },
            },
        }),
        new HtmlWebpackPlugin({
            template: './public/index.html',
        }),
    ],
};
```

### `shell/src/index.tsx`

```typescript
// Bootstrap pattern - required for Module Federation
import('./bootstrap');
```

### `shell/src/bootstrap.tsx`

```typescript
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

const root = createRoot(document.getElementById('root')!);
root.render(<App />);
```

### `shell/src/App.tsx`

```typescript
import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import './eventBus';  // Initialize cross-MFE event bus

// ─────────────────────────────────────────────────────────────
// LAZY-LOAD MFEs (loaded at runtime!)
// ─────────────────────────────────────────────────────────────
const CatalogPage = lazy(() => import('catalog/CatalogPage'));
const CartPage = lazy(() => import('cart/CartPage'));
const ProfilePage = lazy(() => import('profile/ProfilePage'));

// ─────────────────────────────────────────────────────────────
// ERROR BOUNDARY (fault isolation per MFE)
// ─────────────────────────────────────────────────────────────
class MFEErrorBoundary extends React.Component<
    { mfeName: string; children: React.ReactNode },
    { hasError: boolean }
> {
    state = { hasError: false };
    
    static getDerivedStateFromError() {
        return { hasError: true };
    }
    
    componentDidCatch(error: Error) {
        console.error(`[MFE Error in ${this.props.mfeName}]`, error);
        // In production: send to Sentry with MFE tag
    }
    
    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: 20, background: '#fee' }}>
                    ⚠️ {this.props.mfeName} is temporarily unavailable
                </div>
            );
        }
        return this.props.children;
    }
}

// ─────────────────────────────────────────────────────────────
// HEADER (always present)
// ─────────────────────────────────────────────────────────────
const Header: React.FC = () => {
    const [cartCount, setCartCount] = React.useState(0);
    
    React.useEffect(() => {
        // Listen for cart updates from CartMFE
        const handler = (e: CustomEvent) => {
            setCartCount(e.detail.count);
        };
        window.addEventListener('cart:updated' as any, handler);
        return () => window.removeEventListener('cart:updated' as any, handler);
    }, []);
    
    return (
        <header style={{ padding: 20, background: '#333', color: 'white' }}>
            <Link to="/" style={{ color: 'white', marginRight: 20 }}>Home</Link>
            <Link to="/catalog" style={{ color: 'white', marginRight: 20 }}>Catalog</Link>
            <Link to="/cart" style={{ color: 'white', marginRight: 20 }}>
                Cart ({cartCount})
            </Link>
            <Link to="/profile" style={{ color: 'white' }}>Profile</Link>
        </header>
    );
};

// ─────────────────────────────────────────────────────────────
// APP COMPONENT
// ─────────────────────────────────────────────────────────────
const App: React.FC = () => (
    <BrowserRouter>
        <Header />
        <main style={{ padding: 20 }}>
            <Suspense fallback={<div>Loading...</div>}>
                <Routes>
                    <Route path="/" element={<h1>Welcome!</h1>} />
                    <Route 
                        path="/catalog/*" 
                        element={
                            <MFEErrorBoundary mfeName="Catalog">
                                <CatalogPage />
                            </MFEErrorBoundary>
                        } 
                    />
                    <Route 
                        path="/cart" 
                        element={
                            <MFEErrorBoundary mfeName="Cart">
                                <CartPage />
                            </MFEErrorBoundary>
                        } 
                    />
                    <Route 
                        path="/profile/*" 
                        element={
                            <MFEErrorBoundary mfeName="Profile">
                                <ProfilePage />
                            </MFEErrorBoundary>
                        } 
                    />
                </Routes>
            </Suspense>
        </main>
    </BrowserRouter>
);

export default App;
```

### `shell/src/eventBus.ts`

```typescript
/**
 * Cross-MFE event bus.
 * Lives on window so all MFEs can access it.
 */
class MFEEventBus {
    emit(event: string, data: any) {
        window.dispatchEvent(
            new CustomEvent(`mfe:${event}`, { detail: data })
        );
        console.log(`[EventBus] Emitted mfe:${event}`, data);
    }
    
    on(event: string, handler: (data: any) => void): () => void {
        const wrapped = (e: Event) => handler((e as CustomEvent).detail);
        window.addEventListener(`mfe:${event}`, wrapped);
        return () => window.removeEventListener(`mfe:${event}`, wrapped);
    }
}

// Expose on window for all MFEs to use
declare global {
    interface Window {
        eventBus: MFEEventBus;
    }
}

window.eventBus = new MFEEventBus();
export {};
```

---

## 4. 📦 Catalog Remote MFE

### `mfes/catalog/webpack.config.js`

```javascript
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { ModuleFederationPlugin } = require('webpack').container;

module.exports = {
    entry: './src/index.tsx',
    mode: 'development',
    devServer: {
        port: 3001,
        historyApiFallback: true,
        hot: true,
        headers: {
            'Access-Control-Allow-Origin': '*',
        },
    },
    output: {
        publicPath: 'http://localhost:3001/',
        clean: true,
    },
    resolve: {
        extensions: ['.tsx', '.ts', '.jsx', '.js'],
    },
    module: {
        rules: [
            {
                test: /\.[jt]sx?$/,
                exclude: /node_modules/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['@babel/preset-env', '@babel/preset-react', '@babel/preset-typescript'],
                    },
                },
            },
        ],
    },
    plugins: [
        new ModuleFederationPlugin({
            name: 'catalog',
            filename: 'remoteEntry.js',
            // EXPOSE these modules to consumers
            exposes: {
                './CatalogPage': './src/CatalogPage',
                './ProductCard': './src/ProductCard',
            },
            shared: {
                react: { singleton: true, requiredVersion: '^18.2.0' },
                'react-dom': { singleton: true, requiredVersion: '^18.2.0' },
                'react-router-dom': { singleton: true, requiredVersion: '^6.20.0' },
            },
        }),
        new HtmlWebpackPlugin({ template: './public/index.html' }),
    ],
};
```

### `mfes/catalog/src/CatalogPage.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { Routes, Route, useParams, Link } from 'react-router-dom';

interface Product {
    id: number;
    name: string;
    price: number;
    image: string;
}

const PRODUCTS: Product[] = [
    { id: 1, name: 'iPhone 15', price: 79999, image: '📱' },
    { id: 2, name: 'MacBook Pro', price: 199999, image: '💻' },
    { id: 3, name: 'AirPods', price: 24999, image: '🎧' },
];

const ProductCard: React.FC<{ product: Product }> = ({ product }) => {
    const handleAddToCart = () => {
        // Emit event to other MFEs
        window.eventBus.emit('cart:item-added', {
            productId: product.id,
            name: product.name,
            price: product.price,
            quantity: 1,
        });
        alert(`Added ${product.name} to cart!`);
    };
    
    return (
        <div style={{ border: '1px solid #ccc', padding: 20, margin: 10, borderRadius: 8 }}>
            <div style={{ fontSize: 60, textAlign: 'center' }}>{product.image}</div>
            <h3>{product.name}</h3>
            <p>₹{product.price.toLocaleString()}</p>
            <Link to={`/catalog/${product.id}`}>View Details</Link>
            <br />
            <button onClick={handleAddToCart}>Add to Cart</button>
        </div>
    );
};

const ProductDetail: React.FC = () => {
    const { id } = useParams();
    const product = PRODUCTS.find(p => p.id === Number(id));
    
    if (!product) return <div>Product not found</div>;
    
    return (
        <div>
            <Link to="/catalog">← Back to catalog</Link>
            <h1>{product.image} {product.name}</h1>
            <p>Price: ₹{product.price.toLocaleString()}</p>
            <p>This is the detail page for product {id}.</p>
        </div>
    );
};

const CatalogList: React.FC = () => (
    <div>
        <h1>Catalog</h1>
        <div style={{ display: 'flex', flexWrap: 'wrap' }}>
            {PRODUCTS.map(p => <ProductCard key={p.id} product={p} />)}
        </div>
    </div>
);

// CatalogPage has its OWN routes (independent routing)
const CatalogPage: React.FC = () => (
    <Routes>
        <Route path="/" element={<CatalogList />} />
        <Route path="/:id" element={<ProductDetail />} />
    </Routes>
);

export default CatalogPage;
```

---

## 5. 🛒 Cart Remote MFE

### `mfes/cart/src/CartPage.tsx`

```typescript
import React, { useState, useEffect } from 'react';

interface CartItem {
    productId: number;
    name: string;
    price: number;
    quantity: number;
}

const CartPage: React.FC = () => {
    const [items, setItems] = useState<CartItem[]>([]);
    
    useEffect(() => {
        // Listen for items added from other MFEs (e.g., Catalog)
        const cleanup = window.eventBus.on('cart:item-added', (item: CartItem) => {
            setItems(prev => {
                const existing = prev.find(i => i.productId === item.productId);
                if (existing) {
                    return prev.map(i => 
                        i.productId === item.productId 
                            ? { ...i, quantity: i.quantity + item.quantity }
                            : i
                    );
                }
                return [...prev, item];
            });
        });
        
        return cleanup;
    }, []);
    
    // Broadcast cart count to other MFEs (e.g., Header badge)
    useEffect(() => {
        const count = items.reduce((sum, i) => sum + i.quantity, 0);
        window.eventBus.emit('cart:updated', { count });
    }, [items]);
    
    const removeItem = (productId: number) => {
        setItems(prev => prev.filter(i => i.productId !== productId));
    };
    
    const total = items.reduce((sum, i) => sum + i.price * i.quantity, 0);
    
    return (
        <div>
            <h1>Your Cart</h1>
            {items.length === 0 ? (
                <p>Cart is empty</p>
            ) : (
                <>
                    {items.map(item => (
                        <div key={item.productId} style={{ borderBottom: '1px solid #eee', padding: 10 }}>
                            <strong>{item.name}</strong>
                            <span> × {item.quantity}</span>
                            <span> = ₹{(item.price * item.quantity).toLocaleString()}</span>
                            <button onClick={() => removeItem(item.productId)} style={{ marginLeft: 10 }}>
                                Remove
                            </button>
                        </div>
                    ))}
                    <h2>Total: ₹{total.toLocaleString()}</h2>
                    <button onClick={() => alert('Proceeding to checkout!')}>
                        Checkout
                    </button>
                </>
            )}
        </div>
    );
};

export default CartPage;
```

---

## 6. 👤 Profile Remote MFE (Different Tech Stack Demo)

### `mfes/profile/src/ProfilePage.tsx`

```typescript
import React, { useState } from 'react';
import { Routes, Route, Link, useParams } from 'react-router-dom';

const ProfileHome: React.FC = () => (
    <div>
        <h1>Profile</h1>
        <ul>
            <li><Link to="/profile/info">Personal Info</Link></li>
            <li><Link to="/profile/orders">Order History</Link></li>
            <li><Link to="/profile/settings">Settings</Link></li>
        </ul>
    </div>
);

const ProfileInfo: React.FC = () => {
    const [user] = useState({
        name: 'Ashish Chaurasiya',
        email: 'chaurasiya1ashish@gmail.com',
        joined: '2024-01-15',
    });
    
    return (
        <div>
            <Link to="/profile">← Back</Link>
            <h2>Personal Info</h2>
            <p><strong>Name:</strong> {user.name}</p>
            <p><strong>Email:</strong> {user.email}</p>
            <p><strong>Member since:</strong> {user.joined}</p>
        </div>
    );
};

const ProfilePage: React.FC = () => (
    <Routes>
        <Route path="/" element={<ProfileHome />} />
        <Route path="/info" element={<ProfileInfo />} />
        <Route path="/orders" element={<div>Order History (placeholder)</div>} />
        <Route path="/settings" element={<div>Settings (placeholder)</div>} />
    </Routes>
);

export default ProfilePage;
```

---

## 7. 🎨 Shared Design System

### `shared/design-system/package.json`

```json
{
    "name": "@company/design-system",
    "version": "1.0.0",
    "main": "dist/index.js",
    "types": "dist/index.d.ts",
    "files": ["dist"],
    "peerDependencies": {
        "react": "^18.0.0",
        "react-dom": "^18.0.0"
    },
    "scripts": {
        "build": "tsc",
        "storybook": "storybook dev -p 6006"
    }
}
```

### `shared/design-system/src/Button.tsx`

```typescript
import React from 'react';

type Variant = 'primary' | 'secondary' | 'danger';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: Variant;
    children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({ 
    variant = 'primary', 
    children, 
    style,
    ...props 
}) => {
    const styles: Record<Variant, React.CSSProperties> = {
        primary: { background: '#0066cc', color: 'white' },
        secondary: { background: '#666', color: 'white' },
        danger: { background: '#cc0000', color: 'white' },
    };
    
    return (
        <button 
            style={{
                padding: '8px 16px',
                border: 'none',
                borderRadius: 4,
                cursor: 'pointer',
                ...styles[variant],
                ...style,
            }}
            {...props}
        >
            {children}
        </button>
    );
};
```

### Versioning Strategy

```json
// catalog/package.json
{
    "dependencies": {
        "@company/design-system": "^1.0.0"  // Catalog uses v1.0+
    }
}

// cart/package.json
{
    "dependencies": {
        "@company/design-system": "^1.0.0"  // Cart uses v1.0+
    }
}

// Bump design system:
// v1.1.0 - New components added (backward compatible)
// v2.0.0 - Breaking changes (gradual migration)
```

---

## 8. 🚀 Running Everything

### Start All MFEs

```bash
# Terminal 1 - Shell
$ cd shell && npm run start
> Shell running at http://localhost:3000

# Terminal 2 - Catalog
$ cd mfes/catalog && npm run start
> Catalog MFE running at http://localhost:3001

# Terminal 3 - Cart
$ cd mfes/cart && npm run start
> Cart MFE running at http://localhost:3002

# Terminal 4 - Profile
$ cd mfes/profile && npm run start
> Profile MFE running at http://localhost:3003
```

### Open Browser

```
http://localhost:3000

→ Shell loads
→ Header always present
→ Navigate to /catalog → CatalogMFE loaded dynamically
→ Click Add to Cart → event emitted
→ Header badge updates (CartCount via event)
→ Navigate to /cart → CartMFE loaded → shows items
```

### Verify Independent Loading

```bash
# In browser DevTools → Network tab:

When you navigate to /catalog:
   1. Browser requests: http://localhost:3001/remoteEntry.js
   2. Then: http://localhost:3001/src_CatalogPage_tsx.js
   3. CatalogPage rendered

→ Catalog is loaded at runtime, not at build!
→ Catalog could be deployed independently!
```

---

## 9. 🐳 Docker Compose Setup

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  shell:
    build: ./shell
    ports: ["3000:3000"]
    environment:
      - CATALOG_URL=http://catalog:3001
      - CART_URL=http://cart:3002
      - PROFILE_URL=http://profile:3003
    depends_on: [catalog, cart, profile]
  
  catalog:
    build: ./mfes/catalog
    ports: ["3001:3001"]
  
  cart:
    build: ./mfes/cart
    ports: ["3002:3002"]
  
  profile:
    build: ./mfes/profile
    ports: ["3003:3003"]
```

### Dockerfile (per MFE)

```dockerfile
FROM node:20-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Serve via nginx in production
FROM nginx:alpine
COPY --from=0 /app/dist /usr/share/nginx/html
EXPOSE 80
```

---

## 10. 🔄 Independent CI/CD per MFE

### `.github/workflows/catalog-ci.yml`

```yaml
name: Deploy Catalog MFE
on:
  push:
    paths: ['mfes/catalog/**']  # ONLY triggers on catalog changes!
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - run: cd mfes/catalog && npm ci && npm test
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build
        run: |
          cd mfes/catalog
          npm ci
          npm run build
      
      - name: Deploy to S3
        run: |
          aws s3 sync mfes/catalog/dist/ s3://mfe-catalog/${{ github.sha }}/
          # Update the "current" pointer
          aws s3 cp mfes/catalog/dist/remoteEntry.js s3://mfe-catalog/remoteEntry.js
      
      - name: Invalidate CloudFront
        run: |
          aws cloudfront create-invalidation \
            --distribution-id $CF_ID \
            --paths "/remoteEntry.js"
      
      - name: Notify
        run: |
          echo "Catalog deployed!"
          # In production: Slack notification, etc.
```

---

## 11. 🌐 Single-SPA Alternative

### `single-spa-config.ts` (alternative to Module Federation)

```typescript
import { registerApplication, start } from 'single-spa';

registerApplication({
    name: '@org/header',
    app: () => System.import('@org/header'),
    activeWhen: () => true,  // Always active (header on every page)
});

registerApplication({
    name: '@org/catalog',
    app: () => System.import('@org/catalog'),
    activeWhen: ['/catalog'],  // Only when /catalog/*
});

registerApplication({
    name: '@org/cart',
    app: () => System.import('@org/cart'),
    activeWhen: ['/cart', '/checkout'],
});

registerApplication({
    name: '@org/profile',
    app: () => System.import('@org/profile'),
    activeWhen: ['/profile'],
});

start({
    urlRerouteOnly: true,  // Only re-route on URL change
});
```

### Single-SPA App Wrapper

```typescript
// mfes/catalog/src/single-spa-app.ts
import { ReactNetCss } from 'single-spa-react';
import App from './App';

const lifecycles = singleSpaReact({
    React,
    ReactDOM,
    rootComponent: App,
    errorBoundary: (err, info, props) => {
        return <div>Error in Catalog MFE</div>;
    },
});

export const bootstrap = lifecycles.bootstrap;
export const mount = lifecycles.mount;
export const unmount = lifecycles.unmount;
```

---

## 12. 🧪 Testing Micro-frontends

### Unit Tests (per MFE)

```typescript
// mfes/cart/src/CartPage.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import CartPage from './CartPage';

beforeEach(() => {
    // Mock eventBus
    window.eventBus = {
        emit: jest.fn(),
        on: jest.fn(() => () => {}),
    } as any;
});

test('renders empty cart', () => {
    render(<CartPage />);
    expect(screen.getByText(/cart is empty/i)).toBeInTheDocument();
});

test('adds item when event received', () => {
    const { rerender } = render(<CartPage />);
    
    // Simulate event from another MFE
    let handler: any;
    (window.eventBus.on as jest.Mock).mockImplementation((event, h) => {
        handler = h;
        return () => {};
    });
    
    // Trigger the handler
    handler({ productId: 1, name: 'iPhone', price: 79999, quantity: 1 });
    rerender(<CartPage />);
    
    expect(screen.getByText(/iPhone/)).toBeInTheDocument();
});
```

### E2E Tests (across MFEs)

```typescript
// e2e/buy-flow.spec.ts
import { test, expect } from '@playwright/test';

test('full purchase flow across MFEs', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    // 1. Navigate to catalog (loads CatalogMFE)
    await page.click('text=Catalog');
    await expect(page.locator('h1')).toContainText('Catalog');
    
    // 2. Add iPhone to cart (CatalogMFE emits event)
    await page.locator('text=iPhone 15').locator('..').locator('text=Add to Cart').click();
    
    // 3. Header updates (Shell listens to event)
    await expect(page.locator('text=Cart (1)')).toBeVisible();
    
    // 4. Navigate to cart (loads CartMFE)
    await page.click('text=Cart (1)');
    await expect(page.locator('text=iPhone 15')).toBeVisible();
    
    // 5. Checkout
    await page.click('text=Checkout');
});
```

---

## 13. 📊 Monitoring & Debugging

### Error Tracking Per MFE

```typescript
// shared/error-tracking.ts
import * as Sentry from '@sentry/react';

export function setupSentry(mfeName: string) {
    Sentry.init({
        dsn: process.env.SENTRY_DSN,
        environment: process.env.NODE_ENV,
        beforeSend(event) {
            // Tag every error with the MFE name
            event.tags = { ...event.tags, mfe: mfeName };
            return event;
        },
    });
}

// In each MFE's bootstrap:
setupSentry('catalog');  // or 'cart', 'profile', etc.
```

### Bundle Analysis

```bash
# Find duplicate dependencies
$ webpack-bundle-analyzer mfes/catalog/dist/stats.json

# Look for:
# - React loaded multiple times? (singleton broken)
# - Large unused libraries?
# - Code splitting working?
```

---

## 14. 🎓 Migration: SPA → Micro-frontends

### Phase 1: Identify Slice

```
Current: Monolithic React app
   src/
   ├── catalog/   ← Extract this first
   ├── cart/
   ├── profile/
   └── orders/
```

### Phase 2: Carve Out Code

```bash
# Move catalog/ to new repo
$ git clone monolith
$ cd monolith
$ git filter-repo --path src/catalog/ --to-subdirectory-filter mfes/catalog
```

### Phase 3: Add MFE Wrapper

```typescript
// New repo: catalog-mfe/src/CatalogPage.tsx
// Wrap existing code with MFE conventions
// Add Module Federation config
```

### Phase 4: Route Traffic Gradually

```typescript
// In old monolith:
const CatalogPage = useExtractedCatalog 
    ? lazy(() => import('catalog/CatalogPage'))  // Remote
    : InternalCatalog;                            // Old
```

### Phase 5: Decommission

```
Once 100% on new MFE:
   - Remove old code from monolith
   - Celebrate 🎉
```

---

## 15. Common Pitfalls & Fixes

### Pitfall 1: React Loaded Twice

```
Symptom: "Hooks can only be called inside a component"

Cause: Two React instances on page

Fix:
   shared: {
       react: { 
           singleton: true,      ← REQUIRED
           requiredVersion: '^18.0.0' 
       }
   }
```

### Pitfall 2: CSS Conflicts

```
Symptom: Catalog's styles bleed into Cart

Fix: Use CSS Modules or Shadow DOM
   .catalog-button { ... }  ← prefixed
   
   Or:
   <ShadowRoot> ← isolation
       <CartContent />
   </ShadowRoot>
```

### Pitfall 3: Memory Leaks

```
Symptom: App slows down over time

Cause: Event listeners not cleaned up

Fix: Always return cleanup from useEffect
   useEffect(() => {
       const cleanup = window.eventBus.on('event', handler);
       return cleanup;  ← REQUIRED
   }, []);
```

### Pitfall 4: Slow First Paint

```
Symptom: Blank screen for 3 seconds

Cause: Loading multiple MFEs in parallel

Fix:
   - Server-side render the shell
   - Lazy load below-fold MFEs
   - Use loading skeletons
```

---

## 16. Key Learnings Summary

```
✅ Shell + Remotes pattern via Module Federation
✅ Each MFE independently developed & deployed
✅ Cross-MFE communication via event bus
✅ Shared design system for visual consistency
✅ Singleton React via Module Federation
✅ Error boundaries for fault isolation
✅ Independent CI/CD per MFE
✅ Bundle optimization is critical
✅ Start monolithic, extract when justified

🎯 The key insight:
   Micro-frontends mirror microservices on frontend.
   Each team owns full-stack vertical slice.
```

---

## 🎬 What's Next?

In **Lecture 5**, we'll explore **real-world use cases** for all these patterns — SaaS, fintech, e-commerce, social media — and see how they combine in production.

> **Next lecture:** [05_Real_World_Use_Cases.md](05_Real_World_Use_Cases.md)

---

## 📚 Try It Yourself

1. Add a **Search MFE** that emits search events to all MFEs
2. Implement **server-side rendering** of the shell for SEO
3. Build a **mobile-only MFE** that loads conditionally
4. Add **A/B testing** by loading different MFE versions
5. Migrate one MFE from React to Vue (polyglot demo)
