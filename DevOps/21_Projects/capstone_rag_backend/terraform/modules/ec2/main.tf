variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  type        = string
  description = "Public subnet to launch the instance into"
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "Your IP in CIDR form, e.g. '203.0.113.7/32' — never 0.0.0.0/0"
}

variable "key_name" {
  type        = string
  description = "Existing EC2 key pair name for SSH access"
}

# ── Security group: 22 (locked to caller IP), 80, 443 only ─────────────────

resource "aws_security_group" "app" {
  name_prefix = "${var.environment}-rag-backend-app-"
  vpc_id      = var.vpc_id

  ingress {
    description = "SSH — restricted to operator IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  ingress {
    description = "HTTP — redirected to HTTPS by nginx"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.environment}-rag-backend-app-sg" }
}

# ── EC2 instance running the Docker image built by the CI pipeline ─────────

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.app.id]
  key_name               = var.key_name

  # Installs Docker + pulls the image the CI pipeline (Project 2) built.
  # The actual .env values are injected via SSM Parameter Store at boot,
  # never baked into this script or the AMI.
  user_data = <<-EOF
    #!/bin/bash
    set -euxo pipefail
    apt-get update
    apt-get install -y docker.io docker-compose-plugin
    systemctl enable --now docker
    mkdir -p /opt/rag-backend
    # Real deploy: aws ssm get-parameters-by-path --path /rag-backend/${var.environment} > /opt/rag-backend/.env
    # docker compose -f /opt/rag-backend/docker-compose.prod.yml up -d
  EOF

  tags = { Name = "${var.environment}-rag-backend-app" }
}

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"

  tags = { Name = "${var.environment}-rag-backend-eip" }
}

output "public_ip" {
  value = aws_eip.app.public_ip
}

output "security_group_id" {
  value = aws_security_group.app.id
}
