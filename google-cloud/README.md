# Google Cloud Run Deployment

This folder contains minimal tooling and documentation to deploy QuickTone to Google Cloud Run from GitHub Actions.

## Overview
- Container image is built from the root Dockerfile.
- Image is pushed to Google Artifact Registry (GAR).
- Service is deployed to Cloud Run using `gcloud`.
- The GitHub Actions workflow file: `.github/workflows/deploy-cloudrun.yml`.

You can use either Workload Identity Federation (recommended) or a Service Account key for GitHub authentication.

## Prerequisites
1. Enable required services in your GCP project:
   ```bash
   gcloud services enable \
     artifactregistry.googleapis.com \
     run.googleapis.com \
     iamcredentials.googleapis.com
   ```
2. Create an Artifact Registry repository (if not existing):
   ```bash
   gcloud artifacts repositories create quicktone \
     --repository-format=docker \
     --location=us-central1 \
     --description="QuickTone images"
   ```
   - Replace `us-central1` with your region.
   - You can use any repository name; remember to set GAR_REPO accordingly.
3. Create a service account and grant minimal roles:
   ```bash
   gcloud iam service-accounts create github-actions \
     --display-name "GitHub Actions Deploy"

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com \
     --role roles/run.admin

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com \
     --role roles/artifactregistry.writer

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com \
     --role roles/iam.serviceAccountUser
   ```

## GitHub configuration
You can configure authentication via:

- Workload Identity Federation (recommended, keyless):
  1. Create a Workload Identity Pool and Provider.
  2. Allow the provider to impersonate the service account.
  3. Save the following repository secrets:
     - `GCP_WORKLOAD_IDENTITY_PROVIDER` (full resource name)
     - `GCP_SERVICE_ACCOUNT_EMAIL` (e.g., `github-actions@PROJECT_ID.iam.gserviceaccount.com`)

- Or Service Account key (simpler, but less secure):
  1. Create a JSON key for the service account.
  2. Save the key file content in secret `GCP_SA_KEY`.

Additionally, set the following as GitHub Repository Variables (preferred) or Secrets:
- `GCP_PROJECT_ID`
- `GCP_REGION` (e.g., `us-central1`)
- `GAR_REPO` (e.g., `quicktone`)
- `CLOUD_RUN_SERVICE` (e.g., `quicktone`)
- Optional: `GAR_HOST` to override default `<region>-docker.pkg.dev`.

## Running the workflow
- On push to `main` (or tags like `vX.Y.Z`), the workflow will build, push, and deploy.
- You can also trigger it manually via the "Run workflow" button and optionally provide `image_tag`.

## Cloud Run settings
The workflow deploys with:
- `--port 8080`
- `--allow-unauthenticated`
- Env vars: `QT_ENV=prod`, `QT_MODEL_DEFAULT=vader`, `QT_MODEL_WARM_ON_STARTUP=true`

To customize CPU/memory/concurrency, you can update the workflow command or use the example service manifest (`service.yaml`) and deploy with:
```bash
gcloud run services replace google-cloud/service.yaml --region $GCP_REGION --project $GCP_PROJECT_ID
```

## Verify deployment
After deployment, the action prints the service URL. You can test:
```bash
curl -s $SERVICE_URL/health | jq
```

## Local test build
```bash
docker build -t quicktone:local .
docker run -p 8080:8080 quicktone:local
```
