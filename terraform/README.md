# Terraform Infrastructure

Google Cloud Platform infrastructure configuration for the Fides AI Assistant platform.

## 📋 Resources

- **GKE Autopilot Cluster** - `fides-production` in `europe-west3`
- **VPC Network** - Custom network with pod/service ranges
- **Firewall Rules** - Health checks and load balancing
- **GCS State Backend** - `gen-lang-client-0859968110-tfstate`

## 🚀 Infrastructure Management

The GKE cluster and network infrastructure are provisioned using this Terraform configuration. The CI/CD pipeline ([.github/workflows/cloud-deploy.yml](../.github/workflows/cloud-deploy.yml)) deploys applications to the cluster created by these scripts.

**State Backend**: Remote state stored in GCS bucket `gen-lang-client-0859968110-tfstate` (created via `bootstrap/` directory).

**Target Cluster**: `fides-production` in `europe-west3` region.

## 📝 Configuration

Key variables defined in `variables.tf`:

- `project_id`: `gen-lang-client-0859968110`
- `region`: `europe-west3`
- `cluster_name`: `fides-production`

## 📂 Directory Structure

```
terraform/
├── main.tf           # Main infrastructure definition
├── variables.tf      # Input variables
├── outputs.tf        # Output values
├── bootstrap/        # State backend setup
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
└── README.md         # This file
```

## 🔐 State Management

- **Backend**: GCS bucket `gen-lang-client-0859968110-tfstate`
- **State Path**: `terraform/state/default.tfstate`
- **Encryption**: Google-managed
- **Versioning**: Enabled

## 🔄 CI/CD Integration

The GitHub Actions workflow uses these Terraform-managed resources:

- **Cluster**: `fides-production`
- **Region**: `europe-west3`
- **Project**: `gen-lang-client-0859968110`

See [.github/workflows/cloud-deploy.yml](../.github/workflows/cloud-deploy.yml) for deployment automation.

## 📚 Related Documentation

- [Main Project README](../README.md)
- [Helm Charts README](../helm/README.md)
