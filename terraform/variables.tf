variable "resource_group_name" {
  description = "Resource group for all project resources"
  type        = string
  default     = "fastapi-aks-jenkins-rg"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "cluster_name" {
  description = "AKS cluster name"
  type        = string
  default     = "fastapi-aks"
}
