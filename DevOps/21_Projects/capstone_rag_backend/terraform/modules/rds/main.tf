variable "environment" {
  type = string
}

variable "db_subnet_group_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "app_security_group_id" {
  type        = string
  description = "Only the app's SG may reach Postgres — nothing else"
}

variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Set via TF_VAR_db_password env var or a secrets manager — NEVER in a .tfvars file committed to Git"
}

# ── DB security group: only the app SG may connect, nothing else ───────────

resource "aws_security_group" "db" {
  name_prefix = "${var.environment}-rag-backend-db-"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Postgres — app tier only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.app_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.environment}-rag-backend-db-sg" }
}

resource "aws_db_instance" "main" {
  identifier     = "${var.environment}-rag-backend-db"
  engine         = "postgres"
  engine_version = "16"

  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  storage_encrypted = true

  db_name  = "ragdb"
  username = "rag"
  password = var.db_password # sensitive — sourced from a variable, never hardcoded

  db_subnet_group_name   = var.db_subnet_group_name
  vpc_security_group_ids = [aws_security_group.db.id]

  backup_retention_period = var.environment == "prod" ? 7 : 1
  skip_final_snapshot     = var.environment != "prod"
  deletion_protection     = var.environment == "prod"

  tags = { Name = "${var.environment}-rag-backend-db" }
}

output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "db_name" {
  value = aws_db_instance.main.db_name
}
