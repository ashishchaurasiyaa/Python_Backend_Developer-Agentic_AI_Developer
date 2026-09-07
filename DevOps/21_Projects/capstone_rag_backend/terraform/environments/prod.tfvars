environment        = "prod"
instance_type      = "t3.small"
db_instance_class  = "db.t3.small"
key_name           = "CHANGE-ME-your-ec2-keypair-name"
allowed_ssh_cidr   = "CHANGE-ME-your-ip/32"

# db_password: same rule as dev — never here, pass via TF_VAR_db_password
# or (better for prod) source it from AWS Secrets Manager in CI.
