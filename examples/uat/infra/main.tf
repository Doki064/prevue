terraform {
  required_version = ">= 1.5.0"
}

resource "null_resource" "uat_placeholder" {
  triggers = {
    fixture = "phase-2-uat-multi-domain"
  }
}
