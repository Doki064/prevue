---
name: Infrastructure-as-Code Safety
description: Review Terraform / Dockerfiles / K8s manifests for security and reliability.
applies-to:
  - "**/*.tf"
  - "terraform/**"
  - "**/Dockerfile"
  - "**/k8s/**"
---
- No hardcoded secrets in IaC; use secret stores / variables.
- Least privilege: IAM roles/policies, security-group rules, and RBAC are scoped — flag `0.0.0.0/0` ingress and wildcard permissions.
- Containers: pinned base-image tags (not `latest`), non-root user, minimal capabilities.
- Resources have sane limits/requests; storage isn't public by default.
