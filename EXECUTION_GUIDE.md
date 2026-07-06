# Track A — FastAPI on AKS with Jenkins
## Complete Step-by-Step Execution Guide

---

## PHASE 1 — Local setup and testing

### Step 1.1 — Create GitHub repo
1. Go to github.com → New repository
2. Name: `fastapi-aks-jenkins`
3. Visibility: Public (needed for GHCR free tier)
4. No README (you will push your own)
5. Clone locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/fastapi-aks-jenkins.git
   cd fastapi-aks-jenkins
   ```

### Step 1.2 — Copy all project files into the cloned repo
Copy every file from the structure above into this folder.
Replace YOUR_GITHUB_USERNAME in:
- `helm-charts/fastapi-app/values.yaml` (image.repository line)
- `Jenkinsfile` (GITHUB_USER variable)

### Step 1.3 — Test locally
```bash
python -m venv venv
source venv/Scripts/activate      # Git Bash on Windows
pip install -r requirements-dev.txt
pytest app/tests/ -v
flake8 app/ --max-line-length=100 --exclude=__pycache__
```
All tests must pass before pushing.

### Step 1.4 — Test Docker locally
```bash
docker build -t fastapi-app:local .
docker run -p 8000:8000 fastapi-app:local
curl http://localhost:8000/health
curl http://localhost:8000/api/items
```

### Step 1.5 — Push to GitHub
```bash
git add .
git commit -m "Initial FastAPI app with Helm chart and Jenkinsfile"
git push origin main
```

---

## PHASE 2 — Enable GHCR (GitHub Container Registry)

### Step 2.1 — Create GitHub Personal Access Token
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Note: `jenkins-ghcr-token`
4. Expiration: 90 days
5. Scopes — check ALL of these:
   - `repo` (full)
   - `write:packages`
   - `read:packages`
   - `delete:packages`
6. Click Generate — COPY THE TOKEN IMMEDIATELY (shown only once)
7. Save it somewhere safe — you will need it for Jenkins credentials

### Step 2.2 — Make your GHCR packages public (optional but easier)
After first push via Jenkins:
1. github.com → Your profile → Packages
2. Click `fastapi-app` → Package settings
3. Change visibility to Public

---

## PHASE 3 — Provision AKS with Terraform

### Step 3.1 — Create Terraform state storage
```bash
az login
az account set --subscription "YOUR_SUBSCRIPTION_ID"

az group create --name tfstate-rg --location eastus

az storage account create \
  --name tfstatejenkins$RANDOM \
  --resource-group tfstate-rg \
  --sku Standard_LRS

az storage container create \
  --name tfstate \
  --account-name <the-name-from-above>
```
Note the storage account name — paste it into terraform/main.tf backend block.

### Step 3.2 — Update terraform/main.tf
Open terraform/main.tf and replace:
```
storage_account_name = "REPLACE_WITH_YOUR_STORAGE_ACCOUNT"
```
with your actual storage account name.

### Step 3.3 — Run Terraform
```bash
cd terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```
This takes 8-12 minutes. AKS cluster creation is the slow part.

### Step 3.4 — Connect kubectl to AKS
```bash
az aks get-credentials \
  --resource-group fastapi-aks-jenkins-rg \
  --name fastapi-aks

kubectl get nodes
```
You should see 2 nodes with STATUS=Ready.

### Step 3.5 — Apply Kubernetes namespaces and RBAC
```bash
cd ..   # back to project root
kubectl apply -f k8s/setup.yaml
kubectl get namespaces
kubectl get serviceaccount jenkins-deployer -n jenkins
```

---

## PHASE 4 — Install NGINX Ingress Controller

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.metrics.enabled=true \
  --wait

# Get the external IP (save this — it's your ALB entry point)
kubectl get svc ingress-nginx-controller -n ingress-nginx
```
Wait until EXTERNAL-IP shows a real IP address (not <pending>). Takes 2-3 minutes.

---

## PHASE 5 — Install Metrics Server (needed for HPA)

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verify
kubectl top nodes
```

---

## PHASE 6 — Install Jenkins on AKS

### Step 6.1 — Install Jenkins via Helm
```bash
helm repo add jenkins https://charts.jenkins.io
helm repo update

helm install jenkins jenkins/jenkins \
  --namespace jenkins \
  --set controller.serviceType=LoadBalancer \
  --set controller.adminPassword=DevOps@2024 \
  --set persistence.enabled=true \
  --set persistence.size=10Gi \
  --set controller.resources.requests.cpu=500m \
  --set controller.resources.requests.memory=1Gi \
  --wait --timeout 10m
```

### Step 6.2 — Get Jenkins external IP
```bash
kubectl get svc jenkins -n jenkins
```
Wait for EXTERNAL-IP. Then open: http://<EXTERNAL-IP>:8080

### Step 6.3 — Login
- Username: `admin`
- Password: `DevOps@2024`

### Step 6.4 — Install required Jenkins plugins
Go to: Manage Jenkins → Plugins → Available plugins
Search and install each one:
- `Kubernetes` (allows Jenkins to run agents as pods)
- `Pipeline` (if not already installed)
- `Git`
- `GitHub`
- `Docker Pipeline`
- `JUnit` (for test results)
- `Credentials Binding`

Click "Install" → check "Restart Jenkins when installation is complete"

### Step 6.5 — Configure Kubernetes cloud in Jenkins
Manage Jenkins → Clouds → New Cloud → Kubernetes

Fill in:
- Name: `kubernetes`
- Kubernetes URL: `https://kubernetes.default.svc`
- Namespace: `jenkins`
- Jenkins URL: `http://jenkins.jenkins.svc.cluster.local:8080`
- Click Test Connection — should say "Connected to Kubernetes..."
- Save

### Step 6.6 — Add GitHub token credential
Manage Jenkins → Credentials → System → Global credentials → Add Credentials

- Kind: `Secret text`
- Secret: (paste your GitHub PAT from Phase 2)
- ID: `github-token`
- Description: `GitHub GHCR token`
- Save

---

## PHASE 7 — Create Jenkins Pipeline

### Step 7.1 — Create new Pipeline job
Jenkins dashboard → New Item
- Name: `fastapi-aks-pipeline`
- Type: Pipeline
- OK

### Step 7.2 — Configure the pipeline
Under Pipeline section:
- Definition: `Pipeline script from SCM`
- SCM: `Git`
- Repository URL: `https://github.com/YOUR_USERNAME/fastapi-aks-jenkins.git`
- Branch: `*/main`
- Script Path: `Jenkinsfile`
- Save

### Step 7.3 — Create GHCR secret in Kubernetes
(So pods can pull the image from GHCR)
```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_PAT \
  --namespace fastapi-staging

kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_PAT \
  --namespace fastapi-prod
```

### Step 7.4 — Run the pipeline
Jenkins dashboard → `fastapi-aks-pipeline` → Build Now

Watch the stages:
- Checkout ✅
- Test ✅
- Security scan ✅
- Build and push to GHCR ✅
- Deploy to staging ✅
- Smoke test staging ✅
- Approval gate ⏸️ (click Approve in Jenkins UI)
- Deploy to production ✅
- Verify production ✅

---

## PHASE 8 — Verify the deployment

```bash
# Check pods
kubectl get pods -n fastapi-staging
kubectl get pods -n fastapi-prod

# Check services
kubectl get svc -n fastapi-staging
kubectl get svc -n fastapi-prod

# Check HPA
kubectl get hpa -n fastapi-staging
kubectl get hpa -n fastapi-prod

# Check ingress
kubectl get ingress -n fastapi-staging
kubectl get ingress -n fastapi-prod

# Port-forward and test
kubectl port-forward svc/fastapi-prod-svc 8000:8000 -n fastapi-prod &
curl http://localhost:8000/health
curl http://localhost:8000/api/items
curl -X POST http://localhost:8000/api/items \
  -H "Content-Type: application/json" \
  -d '{"name":"TestItem","description":"Testing prod","price":9.99}'
```

---

## PHASE 9 — HPA autoscaling demo

```bash
# Watch HPA in one terminal
kubectl get hpa -n fastapi-prod --watch

# In another terminal — run a load test
kubectl run load-test \
  --image=busybox \
  --restart=Never \
  -n fastapi-prod \
  -- /bin/sh -c \
  "while true; do wget -q -O- http://fastapi-prod-svc:8000/api/items; done"

# Watch pods scale up (takes 1-2 minutes to trigger)
kubectl get pods -n fastapi-prod --watch

# Stop load test
kubectl delete pod load-test -n fastapi-prod
```

---

## PHASE 10 — Prometheus + Grafana monitoring

```bash
helm repo add prometheus-community \
  https://prometheus-community.github.io/helm-charts
helm repo update

helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.service.type=LoadBalancer \
  --set grafana.adminPassword=Grafana@2024 \
  --wait --timeout 10m

# Get Grafana IP
kubectl get svc monitoring-grafana -n monitoring
```

Open Grafana at http://<GRAFANA-IP>:80
Login: admin / Grafana@2024

Import these dashboard IDs (Dashboards → Import):
- `6417` — Kubernetes pods overview
- `3119` — Kubernetes cluster monitoring
- `11074` — Node exporter full

---

## PHASE 11 — Rollback demo

### Introduce a bug
Edit `app/routes/health.py`:
```python
@router.get("/health")
def health():
    raise Exception("Simulated failure!")
    return {"status": "healthy", "version": "1.0.0"}
```
Push → Jenkins pipeline runs → approve production gate → prod is broken.

### Manual rollback via Helm
```bash
# See all releases
helm history fastapi-prod -n fastapi-prod

# Rollback to previous release
helm rollback fastapi-prod -n fastapi-prod

# Verify
kubectl rollout status deployment/fastapi-prod -n fastapi-prod
kubectl port-forward svc/fastapi-prod-svc 8000:8000 -n fastapi-prod &
curl http://localhost:8000/health
```

### Fix the bug and push
```python
@router.get("/health")
def health():
    return {"status": "healthy", "version": "1.0.0"}
```
```bash
git add . && git commit -m "fix: restore health endpoint" && git push
```

---

## PHASE 12 — Cleanup (terraform destroy)

When you are done with Track A:
```bash
# Remove Helm releases first
helm uninstall jenkins -n jenkins
helm uninstall monitoring -n monitoring
helm uninstall ingress-nginx -n ingress-nginx
helm uninstall fastapi-staging -n fastapi-staging
helm uninstall fastapi-prod -n fastapi-prod

# Destroy all Azure infrastructure
cd terraform
terraform destroy -auto-approve

# Verify resource group is gone
az group list --query "[?name=='fastapi-aks-jenkins-rg']"
```

---

## Key commands reference

```bash
# Kubernetes
kubectl get pods -n fastapi-prod
kubectl get pods -n fastapi-staging
kubectl describe pod <pod-name> -n fastapi-prod
kubectl logs <pod-name> -n fastapi-prod
kubectl exec -it <pod-name> -n fastapi-prod -- /bin/sh

# Helm
helm list -A                              # all releases
helm history fastapi-prod -n fastapi-prod # release history
helm rollback fastapi-prod -n fastapi-prod # rollback
helm template fastapi-app ./helm-charts/fastapi-app  # dry-run

# HPA
kubectl get hpa -A
kubectl describe hpa fastapi-prod-hpa -n fastapi-prod

# Jenkins
kubectl get pods -n jenkins
kubectl logs -f <jenkins-pod> -n jenkins
```
