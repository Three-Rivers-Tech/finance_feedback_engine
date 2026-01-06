# =============================================================================
# Networking Module Outputs
# =============================================================================

output "network_cidr" {
  description = "Network CIDR block"
  value       = var.network_cidr
}

output "dns_records" {
  description = "Required DNS A records for ingress endpoints"
  value = [
    for domain in var.domain_names : {
      name  = domain
      type  = "A"
      value = var.ingress_ip
      ttl   = 300
    }
  ]
}

output "dns_records_cloudflare" {
  description = "DNS records formatted for Cloudflare CLI/API"
  value = var.cloudflare_zone_id != "" ? [
    for domain in var.domain_names :
    "cloudflare dns create ${var.cloudflare_zone_id} --type A --name ${domain} --content ${var.ingress_ip} --ttl 300"
  ] : []
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
    class     = var.ingress_class
    ip        = var.ingress_ip
    hosts     = var.domain_names
    namespace = var.ingress_namespace
  }
}

output "network_summary" {
  description = "Network configuration summary for documentation"
  value = {
    environment  = var.environment
    cluster_name = var.cluster_name
    cidr_block   = var.network_cidr
    dns_servers  = var.dns_servers
    ingress_ip   = var.ingress_ip
  }
}
