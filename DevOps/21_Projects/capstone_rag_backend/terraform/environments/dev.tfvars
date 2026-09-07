environment        = "dev"
instance_type      = "t3.micro"
db_instance_class  = "db.t3.micro"
key_name           = "CHANGE-ME-your-ec2-keypair-name"
allowed_ssh_cidr   = "CHANGE-ME-your-ip/32"   # e.g. curl ifconfig.me, then append /32

# db_password is deliberately NOT set here — pass it at apply time:
#   TF_VAR_db_password="$(openssl rand -base64 24)" terraform apply -var-file=environments/dev.tfvars
