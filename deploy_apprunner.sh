#!/usr/bin/env bash
#
# Deploy the mock Cisco Meraki API to AWS App Runner via ECR.
#
# Builds the Dockerfile, pushes it to ECR, and creates (or updates) an
# App Runner service. MERAKI_API_KEY is always set on the service so the
# CSP Mock Deployer can fetch a non-empty credential via the provider API.
#
# Prereqs: authenticated AWS CLI, Docker running.
# Usage:   ./deploy_apprunner.sh
#
# To override the pinned API key:
#   MERAKI_API_KEY=<your-key> ./deploy_apprunner.sh
#
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
SERVICE="${SERVICE_NAME:-mock-meraki-api}"
REPO="${ECR_REPO:-mock-meraki-api}"
TAG="${IMAGE_TAG:-latest}"
ACCESS_ROLE_NAME="AppRunnerECRAccessRole"

# Fixed API key — must match what the CSP credential stores.
# Override by exporting MERAKI_API_KEY before running this script.
MERAKI_API_KEY="${MERAKI_API_KEY:-e07e2d23969da5609fea910283bbf254a121b94d}"

cd "$(dirname "$0")"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_URI="${ECR_URI}/${REPO}:${TAG}"
echo "==> Account ${ACCOUNT_ID} | region ${REGION} | image ${IMAGE_URI}"

# 1. ECR repo ------------------------------------------------------------------
aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO" --region "$REGION" >/dev/null
echo "==> ECR repo ready: ${REPO}"

# 2. Build + push (App Runner needs linux/amd64) --------------------------------
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ECR_URI"
# Intermediate tag avoids zsh ':l' modifier expansion bug on filenames with colons.
docker build --no-cache --platform linux/amd64 -t mock-meraki-build .
docker tag mock-meraki-build "$IMAGE_URI"
docker push "$IMAGE_URI"
echo "==> Pushed ${IMAGE_URI}"

# 3. App Runner ECR access role ------------------------------------------------
if ! aws iam get-role --role-name "$ACCESS_ROLE_NAME" >/dev/null 2>&1; then
  echo "==> Creating IAM role ${ACCESS_ROLE_NAME}"
  aws iam create-role --role-name "$ACCESS_ROLE_NAME" \
    --assume-role-policy-document '{
      "Version":"2012-10-17",
      "Statement":[{"Effect":"Allow","Principal":{"Service":"build.apprunner.amazonaws.com"},"Action":"sts:AssumeRole"}]
    }' >/dev/null
  aws iam attach-role-policy --role-name "$ACCESS_ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess >/dev/null
  echo "    waiting for role to propagate..."; sleep 10
fi
ACCESS_ROLE_ARN="$(aws iam get-role --role-name "$ACCESS_ROLE_NAME" --query Role.Arn --output text)"

# 4. Create or update the service ----------------------------------------------
SERVICE_ARN="$(aws apprunner list-services --region "$REGION" \
  --query "ServiceSummaryList[?ServiceName=='${SERVICE}'].ServiceArn | [0]" --output text)"

echo "==> Pinning MERAKI_API_KEY on the service"

SOURCE_CONFIG=$(cat <<JSON
{
  "AuthenticationConfiguration": {"AccessRoleArn": "${ACCESS_ROLE_ARN}"},
  "AutoDeploymentsEnabled": true,
  "ImageRepository": {
    "ImageIdentifier": "${IMAGE_URI}",
    "ImageRepositoryType": "ECR",
    "ImageConfiguration": {
      "Port": "8080",
      "RuntimeEnvironmentVariables": {
        "MERAKI_API_KEY": "${MERAKI_API_KEY}"
      }
    }
  }
}
JSON
)

if [ "$SERVICE_ARN" = "None" ] || [ -z "$SERVICE_ARN" ]; then
  echo "==> Creating App Runner service ${SERVICE}"
  SERVICE_ARN="$(aws apprunner create-service --region "$REGION" \
    --service-name "$SERVICE" \
    --source-configuration "$SOURCE_CONFIG" \
    --instance-configuration '{"Cpu":"256","Memory":"512"}' \
    --health-check-configuration '{"Protocol":"HTTP","Path":"/","Interval":10,"Timeout":5,"HealthyThreshold":1,"UnhealthyThreshold":5}' \
    --query Service.ServiceArn --output text)"
else
  echo "==> Updating existing service ${SERVICE}"
  aws apprunner update-service --region "$REGION" \
    --service-arn "$SERVICE_ARN" \
    --source-configuration "$SOURCE_CONFIG" >/dev/null
  echo "==> Waiting for update to settle, then forcing image re-pull..."
  aws apprunner wait service-updated --region "$REGION" --service-arn "$SERVICE_ARN" 2>/dev/null || sleep 20
  aws apprunner start-deployment --region "$REGION" --service-arn "$SERVICE_ARN" >/dev/null
fi

# 5. Wait for RUNNING and print the URL ----------------------------------------
echo "==> Waiting for service to reach RUNNING (this takes a few minutes)..."
while true; do
  STATUS="$(aws apprunner describe-service --region "$REGION" --service-arn "$SERVICE_ARN" --query Service.Status --output text)"
  echo "    status: ${STATUS}"
  case "$STATUS" in
    RUNNING) break ;;
    CREATE_FAILED|UPDATE_FAILED|DELETE_FAILED) echo "!! deployment failed"; exit 1 ;;
  esac
  sleep 15
done

URL="$(aws apprunner describe-service --region "$REGION" --service-arn "$SERVICE_ARN" --query Service.ServiceUrl --output text)"
echo ""
echo "============================================================"
echo " Service URL: https://${URL}"
echo " MERAKI_API_KEY: ${MERAKI_API_KEY}"
echo "============================================================"
