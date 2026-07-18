# Deployment Guide — Docker + AWS Elastic Beanstalk

A step-by-step walkthrough for deploying the Document Analyzer app **yourself**, by hand — no generators, no automation scripts doing the thinking for you. Follow this once end-to-end and you'll understand every piece.

---

## 0. Before you start — requirements checklist

You need, installed and working, before touching any code:

- [ ] **Docker Desktop** (or Docker Engine on Linux) — verify with `docker --version`
- [ ] **AWS account** with billing set up — verify you can log into the AWS Console
- [ ] **AWS CLI v2** — verify with `aws --version`
- [ ] **EB CLI** (`pip install awsebcli --user` or `pipx install awsebcli`) — verify with `eb --version`
- [ ] **IAM user** (not your root account) with programmatic access keys, and at minimum these managed policies attached: `AdministratorAccess-AWSElasticBeanstalk` (or full admin if this is a learning sandbox)
- [ ] A working app locally — frontend + backend running and talking to each other on `localhost` **before** you Dockerize anything
- [ ] Your LLM API key (Anthropic/OpenAI) — never hardcoded, kept in a `.env` file that is in `.gitignore`

If any box above is unchecked, stop and do that first. Deploying a broken or untested app just moves your debugging into the cloud, where it's slower and costs money.

---

## 1. Confirm the app works locally, unpackaged

Run frontend and backend directly (no Docker yet):

```bash
# backend (example: FastAPI)
uvicorn app.main:app --reload --port 8000

# frontend (if separate dev server)
npm run dev
```

Test all three modes (Analyze / Extract / Rewrite) with a real PDF and pasted text. **Do not proceed until this works.** Docker and AWS will only reproduce whatever bugs you deploy with — they don't fix anything.

---

## 2. Write the Dockerfile

Goal: one image that serves both frontend and backend, since Elastic Beanstalk (single-container mode) expects one container listening on one port.

A common pattern — build the frontend as static files, then serve them from the backend:

```dockerfile
# ---- Stage 1: build frontend (skip if you have no separate frontend build step) ----
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend + serve built frontend ----
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=frontend-build /app/dist ./static

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Adjust paths/commands to match your actual project structure and stack (Express instead of FastAPI, etc.) — the shape (multi-stage build, expose one port, bind to `0.0.0.0` not `localhost`) is what matters.

**Why `0.0.0.0` and not `localhost`/`127.0.0.1`:** inside a container, `localhost` refers to the container itself. AWS's load balancer connects from outside the container, so the app must bind to all interfaces.

---

## 3. Build and run the image locally — before AWS

```bash
docker build -t doc-analyzer .
docker run -p 8000:8000 --env-file .env doc-analyzer
```

Open `http://localhost:8000` and re-test all three modes. If it fails here, it will fail on AWS too — this local loop is much faster to debug in.

Common failure points to check:
- Missing `.env` values inside the container (did you pass `--env-file`?)
- Frontend built but backend not serving the `static/` folder correctly (check your static file mount route)
- File upload size limits differing between dev server and production server config

---

## 4. Set up AWS access

1. Log into the **AWS Console** → IAM → create a user with **programmatic access** (access key + secret key). Don't use root credentials for CLI work.
2. Run:
   ```bash
   aws configure
   ```
   Enter your access key, secret key, default region (e.g. `us-east-1`), and output format (`json`).
3. Confirm it works:
   ```bash
   aws sts get-caller-identity
   ```
   This should print your account ID and user ARN — if it errors, your keys or region are wrong.

---

## 5. Set an AWS Budget Alert — do this before deploying anything

Skipping this is how people get surprise bills.

1. AWS Console → **Billing and Cost Management** → **Budgets** → **Create budget**
2. Choose **Cost budget**, set a monthly amount (e.g. $5–10 for a class project)
3. Add an alert threshold at 80% and 100% of that amount, sent to your email
4. Save

---

## 6. Initialize Elastic Beanstalk

From your project root (where the Dockerfile lives):

```bash
eb init
```

You'll be prompted for:
- **Region** — pick the same one you configured in `aws configure`
- **Application name** — e.g. `doc-analyzer`
- **Platform** — choose **Docker**
- **SSH access** — optional, say yes if you want to be able to `eb ssh` in later for debugging

This creates a `.elasticbeanstalk/` folder locally — this is EB CLI's config, not something you deploy.

---

## 7. Create the environment

```bash
eb create doc-analyzer-env
```

This provisions the actual infrastructure: EC2 instance(s), a load balancer, a security group, and a URL. This step takes several minutes — EB is building the environment, not just uploading your code.

---

## 8. Set environment variables (your API key goes here, not in the image)

```bash
eb setenv ANTHROPIC_API_KEY=sk-ant-xxxxxxxx OTHER_VAR=value
```

Verify your backend code reads these via `os.environ` / `process.env` — **never** bake secrets into the Dockerfile or commit them to git. Confirm this by checking your `.dockerignore` and `.gitignore` both exclude `.env`.

---

## 9. Deploy

```bash
eb deploy
```

This zips your project (respecting `.ebignore`, similar to `.gitignore` — create one so you don't upload `node_modules`, `.git`, local `.env`, etc.), uploads it, and Docker-builds it on AWS's side.

---

## 10. Verify it's live

```bash
eb open
```

This opens your public HTTPS URL in the browser. Test all three modes again, on both desktop and a mobile browser. Then check health:

```bash
eb health
eb logs
```

`eb logs` is your first stop if something works locally but not on AWS — mismatched environment variables and file path assumptions (e.g. hardcoded `localhost`) are the two most common causes.

---

## 11. Ongoing workflow

Every time you push a code change:

```bash
eb deploy
```

To tear the environment down when you're done (avoids ongoing charges):

```bash
eb terminate doc-analyzer-env
```

---

## Quick troubleshooting reference

| Symptom | Likely cause |
|---|---|
| Works locally in Docker, fails on EB | Missing env vars — re-check `eb setenv` values |
| 502 Bad Gateway | App not bound to `0.0.0.0`, or not listening on the port EB expects |
| Deploy succeeds but old version still shows | Browser cache — hard refresh, or check `eb status` for the deployed version label |
| Build fails on AWS but not locally | Dockerfile depends on local files excluded by `.ebignore` |
| File uploads fail in production only | Check request size limits in both your app and any reverse proxy config |

---

**The core idea to hold onto:** local Docker run → AWS Docker run should behave identically if your Dockerfile is correct and your env vars are set. Every deployment bug is really one of those two things being slightly wrong.
