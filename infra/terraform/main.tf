terraform {
  required_version = ">= 1.6.0"
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "hireos-ai"
}

resource "aws_s3_bucket" "lakehouse" {
  bucket = "${var.project_name}-lakehouse-demo"
}

output "lakehouse_bucket" {
  value = aws_s3_bucket.lakehouse.bucket
}

