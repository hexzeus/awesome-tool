# 🚀 Deployment Guide - Quick Start

## Step 1: Install Dependencies

```bash
cd my-awesome-tool
pip install -r requirements.txt
```

This installs the new `openai` package.

---

## Step 2: Update Environment Variables

Open `.env` and configure:

```bash
# Your existing Claude key (already set)
ANTHROPIC_API_KEY=sk-ant-api03-...

# OPTIONAL: Add OpenAI key if you want GPT support
OPENAI_API_KEY=sk-proj-...

# Your existing Gumroad product (already set)
GUMROAD_PRODUCT_ID=TEkWoFBy5TwWJJTpwbjQVA==

# NEW: Add tier-specific products when you create them
GUMROAD_PRODUCT_ID_STARTER=your_starter_id
GUMROAD_PRODUCT_ID_PRO=TEkWoFBy5TwWJJTpwbjQVA==
GUMROAD_PRODUCT_ID_UNLIMITED=your_unlimited_id
GUMROAD_PRODUCT_ID_AGENCY=your_agency_id

# Your existing setting (already set)
FREE_USAGE_LIMIT=3
```

---

## Step 3: Test Locally

```bash
# Run the server
uvicorn main:app --reload

# Test in another terminal
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "anthropic_configured": true,
  "gumroad_configured": true,
  "database": "connected",
  "version": "2.0.0"
}
```

---

## Step 4: Test Demo (Rate Limiting)

Try the demo endpoint 4 times to verify rate limiting works:

```bash
# Demo 1 (should work)
curl -X POST http://localhost:8000/api/demo \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Test Co","industry":"Tech","offer":"We help"}'

# Demo 2 (should work)
# Demo 3 (should work)
# Demo 4 (should fail with 429 error)
```

---

## Step 5: Create Gumroad Products

1. Go to https://gumroad.com/products
2. Create 3 NEW products:
   - **Starter** - $29
   - **Unlimited** - $99
   - **Agency** - $199

3. For each product:
   - Set name and description
   - Set price
   - Copy the Product ID
   - Paste into `.env`

**Note:** Your existing $49 product is already set as Professional.

---

## Step 6: Deploy to Render (or your host)

### If using Render:

```bash
# Commit changes
git add .
git commit -m "feat: Add tiered pricing, rate limiting, campaign storage, OpenAI support"
git push origin main
```

Render will auto-deploy.

### Environment Variables on Render:

Make sure these are set in Render dashboard:
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY` (optional)
- `GUMROAD_PRODUCT_ID`
- `GUMROAD_PRODUCT_ID_STARTER`
- `GUMROAD_PRODUCT_ID_PRO`
- `GUMROAD_PRODUCT_ID_UNLIMITED`
- `GUMROAD_PRODUCT_ID_AGENCY`
- `FREE_USAGE_LIMIT=3`

---

## Step 7: Verify Databases Created

After first run, check that these databases exist:

```bash
ls data/
# Should see:
# - usage.db (existing)
# - campaigns.db (new)
# - tiers.db (new)
# - rate_limits.db (new)
```

These are auto-created on first use.

---

## Step 8: Test Production

### Test Demo:
```
https://your-api.onrender.com/api/demo
```

### Test Health:
```
https://your-api.onrender.com/health
```

### Test Campaign Generation:
Use your frontend or Postman with a valid license key.

---

## Step 9: Frontend Updates (TODO)

Your frontend HTML needs updates to use new features:

### 1. Add Model Selector (Optional)

```html
<select x-model="formData.model_provider">
    <option value="claude">Claude Sonnet 4.5</option>
    <option value="openai">GPT-4</option>
</select>
```

### 2. Show Tier Info

```javascript
// In fetchUsage()
if (data.tier) {
    this.tierInfo = data.tier;
    this.showTierBadge = true;
}
```

### 3. Campaign History

```javascript
async loadCampaigns() {
    const response = await fetch(`${this.apiUrl}/api/campaigns`, {
        headers: { 'Authorization': `Bearer ${this.licenseKey}` }
    });
    const data = await response.json();
    this.campaignsList = data.campaigns;
}
```

### 4. Save Campaign

```javascript
async saveCampaign() {
    await fetch(`${this.apiUrl}/api/campaigns`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${this.licenseKey}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            campaign_data: this.result
        })
    });
}
```

---

## Step 10: Monitor

Watch these logs after deployment:

```bash
# Check for errors
tail -f logs/app.log

# Watch for:
# - "Demo: Generating..." (demos working)
# - "Stage 1: Analyzing..." (campaigns generating)
# - Any error traces
```

---

## 🎯 Quick Test Script

Save this as `test_api.sh`:

```bash
#!/bin/bash

API="http://localhost:8000"

echo "Testing health..."
curl $API/health

echo -e "\n\nTesting demo 1..."
curl -X POST $API/api/demo \
  -H "Content-Type: application/json" \
  -d '{"company_name":"TestCo","industry":"SaaS","offer":"We help SaaS companies"}'

echo -e "\n\nTesting demo 2..."
curl -X POST $API/api/demo \
  -H "Content-Type: application/json" \
  -d '{"company_name":"TestCo","industry":"SaaS","offer":"We help SaaS companies"}'

echo -e "\n\nTesting demo 3..."
curl -X POST $API/api/demo \
  -H "Content-Type: application/json" \
  -d '{"company_name":"TestCo","industry":"SaaS","offer":"We help SaaS companies"}'

echo -e "\n\nTesting demo 4 (should fail)..."
curl -X POST $API/api/demo \
  -H "Content-Type: application/json" \
  -d '{"company_name":"TestCo","industry":"SaaS","offer":"We help SaaS companies"}'

echo -e "\n\nDone!"
```

Run with:
```bash
chmod +x test_api.sh
./test_api.sh
```

---

## ✅ Deployment Checklist

- [ ] Installed new dependencies (`pip install -r requirements.txt`)
- [ ] Updated `.env` with all keys
- [ ] Created Gumroad tier products (Starter, Unlimited, Agency)
- [ ] Updated `.env` with new product IDs
- [ ] Tested locally (health, demo, generation)
- [ ] Verified rate limiting works (4th demo fails)
- [ ] Pushed to Git
- [ ] Deployed to production
- [ ] Set environment variables on host
- [ ] Verified production health endpoint
- [ ] Tested production demo
- [ ] Tested production campaign generation
- [ ] Updated frontend (optional for now)
- [ ] Monitored logs for errors
- [ ] Tested all tier products
- [ ] Ready to market! 🎉

---

## 🆘 Troubleshooting

**Error: "ModuleNotFoundError: No module named 'openai'"**
```bash
pip install openai
```

**Error: "Database is locked"**
- Normal for SQLite under heavy load
- Consider PostgreSQL if you hit 1000+ users

**Demo rate limit not working:**
```bash
# Check database exists
ls data/rate_limits.db

# Restart server
ctrl+C
uvicorn main:app --reload
```

**Tier not showing:**
- Legacy users auto-default to "professional"
- This is correct behavior

---

## 📞 Need Help?

If you encounter issues:
1. Check logs
2. Verify `.env` is correct
3. Test health endpoint
4. Check databases exist in `data/`

---

*Ready to launch? Let's go! 🚀*
