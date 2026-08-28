# 🚀 Wave — Free Deployment & Installation Guide

Wave is designed to be hosted **100% for free** or installed as a native app on any mobile or desktop device.

---

## 📱 Option 1: Install as a Native App on iPhone, Android & Mac (PWA — Free & Instant)

Wave is a Progressive Web App (PWA). You can install it directly onto your phone or computer with a native app icon and zero app store fees!

### On iPhone / iPad (Safari):
1. Open **http://localhost:8000** (or your deployed URL) in Safari.
2. Tap the **Share** button (the box with an upward arrow at the bottom).
3. Scroll down and tap **"Add to Home Screen"**.
4. Tap **Add**. Wave is now installed on your home screen like any Apple App Store app!

### On Android (Chrome):
1. Open your Wave URL in Chrome.
2. Tap the 3 dots menu (⋮) in the top right.
3. Tap **"Install App"** or **"Add to Home Screen"**.
4. The Wave app icon will appear in your app drawer!

### On Mac / Windows (Chrome / Edge / Safari):
1. Open your Wave URL in Chrome or Edge.
2. Click the **Install** icon on the right side of the address bar.
3. Wave runs in its own dedicated, standalone desktop window.

---

## ☁️ Option 2: Deploy Free on Render.com (Free Web Service + Free URL)

[Render.com](https://render.com) offers free web services that can host the FastAPI backend and frontend together under an `onrender.com` domain with free SSL!

### Steps:
1. **Push your code to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of Wave"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/wave.git
   git push -u origin main
   ```
2. Go to [Render Dashboard](https://dashboard.render.com/) and click **New + ➔ Web Service**.
3. Connect your GitHub repository.
4. Set the following settings:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python run.py`
5. Under **Environment Variables**, add:
   - `MONGODB_URI`: `<Your MongoDB Atlas Connection String>`
   - `JWT_SECRET`: `<Your Random Secret String>`
   - `JWT_ALGORITHM`: `HS256`
   - `HOST`: `0.0.0.0`
   - `PORT`: `8000`
6. Click **Create Web Service**. Your app will be live at `https://wave-xxxx.onrender.com`!

---

## ⚡ Option 3: Deploy Free on Railway / Koyeb

1. Go to [Railway.app](https://railway.app) or [Koyeb.com](https://koyeb.com).
2. Click **Deploy from GitHub repo**.
3. Add the `MONGODB_URI` and `JWT_SECRET` variables.
4. Railway automatically detects `Dockerfile` and deploys your service.

---

## 🌐 Option 4: Free Public URL for Local Use (Cloudflare Tunnel)

If you want to run Wave on your Mac but access it from anywhere in the world on your phone for free:
1. Install Cloudflare `cloudflared`:
   ```bash
   brew install cloudflared
   ```
2. Start the tunnel:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
3. Cloudflare gives you a free secure HTTPS URL (e.g. `https://xxxx.trycloudflare.com`) that you can open on your iPhone or Android phone anywhere!

---

## 🐳 Option 5: Run with Docker

```bash
docker build -t wave-music .
docker run -p 8000:8000 --env-file .env wave-music
```
Open `http://localhost:8000`.
