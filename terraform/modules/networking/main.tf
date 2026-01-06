# =============================================================================
# Networking Module - On-Premises Network Configuration
# =============================================================================
# Manages network configuration for on-premises Ubuntu deployment including:
# - DNS records for ingress endpoints
# - Firewall rules (UFW) for ports 80/443
# - Network CIDR allocation
# =============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

# =============================================================================
# DNS CONFIGURATION (External - Manual or via API)
# =============================================================================

# Note: For on-prem deployments, DNS is typically managed externally
# (Cloudflare, Route53, internal DNS server, etc.)
# This module outputs the required DNS records for documentation

locals {
  dns_records = [
    for domain in var.domain_names : {
      name  = domain
      type  = "A"
      value = var.ingress_ip
      ttl   = 300
    }
  ]
}

# =============================================================================
# FIREWALL RULES (UFW on Ubuntu)
# =============================================================================

resource "null_resource" "firewall_rules" {
  count = var.manage_firewall ? 1 : 0

  triggers = {
    rules = jsonencode({
      http  = 80
      https = 443
      ssh   = var.ssh_port
    })
  }

  # Enable UFW and configure rules
  provisioner "local-exec" {
    command = <<-EOT
      # Enable UFW if not already enabled
      sudo ufw --force enable || true

      # Allow SSH (configurable port)
      sudo ufw allow ${var.ssh_port}/tcp comment 'SSH'

      # Allow HTTP (for ACME challenge)
      sudo ufw allow 80/tcp comment 'HTTP - ACME Challenge'

      # Allow HTTPS
      sudo ufw allow 443/tcp comment 'HTTPS'

      # Allow Kubernetes API (if managing K3s/K8s)
      sudo ufw allow 6443/tcp comment 'Kubernetes API'

      # Reload UFW
      sudo ufw reload

      # Show status
      sudo ufw status verbose
    EOT
  }

  # Cleanup: Don't remove firewall rules on destroy (safety measure)
  # Manual cleanup required if needed
}

# =============================================================================
# NETWORK CIDR ALLOCATION
# =============================================================================

# For on-premises deployments, CIDR blocks are typically pre-allocated
# This is primarily for documentation and validation

locals {
  network_config = {
    cidr_block       = var.network_cidr
    subnet_count     = var.subnet_count
    ingress_class    = var.ingress_class
    ingress_ip       = var.ingress_ip
    dns_servers      = var.dns_servers
  }
}

# =============================================================================
# INGRESS IP VERIFICATION
# =============================================================================

# Verify ingress IP is reachable (optional)
resource "null_resource" "ingress_ip_check" {
  count = var.verify_ingress_ip ? 1 : 0

  triggers = {
    ingress_ip = var.ingress_ip
  }

  provisioner "local-exec" {
    command = "ping -c 1 ${var.ingress_ip} || echo 'Warning: Ingress IP ${var.ingress_ip} not reachable'"
  }
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "network_cidr" {
  description = "Network CIDR block"
  value       = var.network_cidr
}

output "dns_records" {
  description = "Required DNS A records for ingress endpoints"
  value       = local.dns_records
}

output "dns_records_cloudflare" {
  description = "DNS records formatted for Cloudflare CLI/API"
  value = [
    for record in local.dns_records :
    "cloudflare dns create ${var.cloudflare_zone_id} --type ${record.type} --name ${record.name} --content ${record.value} --ttl ${record.ttl}"
  ]
}

output "firewall_rules" {
  description = "Configured firewall rules"
  value = {
    ssh   = "${var.ssh_port}/tcp"
    http  = "80/tcp"
    https = "443/tcp"
    k8s   = "6443/tcp"
  }
}

output "ingress_config" {
  description = "Ingress controller configuration"
  value = {
    class = var.ingress_class
    ip    = var.ingress_ip
    hosts = var.domain_names
  }
}

output "network_config" {
  description = "Full network configuration for reference"
  value       = local.network_config
}
