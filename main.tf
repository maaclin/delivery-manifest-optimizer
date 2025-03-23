provider "aws" {
  region = "eu-west-2"  # Change this to your AWS region
}

# 🚀 S3 Bucket for File Storage
resource "aws_s3_bucket" "delivery_manifest" {
  bucket = "delivery-manifest-bucket"

  tags = {
    Name        = "DeliveryManifestBucket"
    Environment = "Dev"
  }
}

# 🚀 DynamoDB Table for Deliveries
resource "aws_dynamodb_table" "delivery_management" {
  name         = "DeliveryManagement"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  tags = {
    Name        = "DeliveryManagementTable"
    Environment = "Dev"
  }
}

# 🚀 DynamoDB Table for Driver Locations
resource "aws_dynamodb_table" "driver_locations" {
  name         = "DriverLocations"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "DriverID"
  range_key    = "Postcode"

  attribute {
    name = "DriverID"
    type = "S"
  }

  attribute {
    name = "Postcode"
    type = "S"
  }

  tags = {
    Name        = "DriverLocationsTable"
    Environment = "Dev"
  }
}

# 🚀 IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_role" {
  name = "lambda_execution_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# 🚀 IAM Policy for Lambda to Access S3 & DynamoDB
resource "aws_iam_policy" "lambda_policy" {
  name        = "lambda_s3_dynamodb_policy"
  description = "Policy for Lambda to access S3 and DynamoDB"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::delivery-manifest-bucket",
          "arn:aws:s3:::delivery-manifest-bucket/*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:Scan", "dynamodb:Query"]
        Resource = [
          aws_dynamodb_table.delivery_management.arn,
          aws_dynamodb_table.driver_locations.arn
        ]
      }
    ]
  })
}

# 🚀 Attach IAM Policy to Lambda Role
resource "aws_iam_role_policy_attachment" "lambda_attach_policy" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# 🚀 Lambda Function for Processing Delivery CSV
resource "aws_lambda_function" "process_delivery_csv" {
  function_name = "ProcessDeliveryCSV"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "python3.9"
  handler       = "lambda_function.lambda_handler"

  filename         = "lambda_package.zip"
  source_code_hash = filebase64sha256("lambda_package.zip")

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.delivery_management.name
    }
  }
}

# 🚀 API Gateway for Fetching Driver ETA
resource "aws_api_gateway_rest_api" "delivery_api" {
  name        = "DeliveryAPI"
  description = "API for fetching driver ETA"
}

resource "aws_api_gateway_resource" "driver_eta" {
  rest_api_id = aws_api_gateway_rest_api.delivery_api.id
  parent_id   = aws_api_gateway_rest_api.delivery_api.root_resource_id
  path_part   = "getDriverETA"
}

resource "aws_api_gateway_method" "driver_eta_get" {
  rest_api_id   = aws_api_gateway_rest_api.delivery_api.id
  resource_id   = aws_api_gateway_resource.driver_eta.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "driver_eta_lambda" {
  rest_api_id = aws_api_gateway_rest_api.delivery_api.id
  resource_id = aws_api_gateway_resource.driver_eta.id
  http_method = aws_api_gateway_method.driver_eta_get.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.process_delivery_csv.invoke_arn
}

# ✅ FIXED: API Gateway Deployment (Removed Duplicate)
resource "aws_api_gateway_deployment" "delivery_api_deploy" {
  depends_on  = [aws_api_gateway_integration.driver_eta_lambda]
  rest_api_id = aws_api_gateway_rest_api.delivery_api.id
}

# ✅ NEW: API Gateway Stage (Replaces Deprecated `stage_name`)
resource "aws_api_gateway_stage" "delivery_api_stage" {
  deployment_id = aws_api_gateway_deployment.delivery_api_deploy.id
  rest_api_id   = aws_api_gateway_rest_api.delivery_api.id
  stage_name    = "dev"
}
