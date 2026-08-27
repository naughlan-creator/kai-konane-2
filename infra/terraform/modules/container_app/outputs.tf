output "id" {
  value       = azurerm_container_app.this.id
  description = "Resource id, for role assignments and diagnostic settings"
}

output "fqdn" {
  value       = azurerm_container_app.this.ingress[0].fqdn
  description = "The app's ingress hostname"
}

output "upstream" {
  value       = "${azurerm_container_app.this.ingress[0].fqdn}:80"
  description = "host:port form for the gateway. Container Apps answers internal traffic on 80 regardless of the container's target port."
}

output "url" {
  value       = "https://${azurerm_container_app.this.ingress[0].fqdn}"
  description = "Public URL. Meaningless for an internal-ingress app, which is why only the gateway's is surfaced at the root."
}
