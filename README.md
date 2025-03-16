# Delivery Manifest Optimizer 🚚

**A serverless AWS-based tool for optimizing last-mile delivery routes.**  
This project processes delivery manifests (CSV files), optimizes driver routes using **Geoapify**, and exports an optimized CSV for each driver.

---

## 📌 Features
- ✅ **AWS Serverless Architecture** (S3, Lambda, DynamoDB)
- ✅ **Automated CSV Processing** when a file is uploaded to S3
- ✅ **Route Optimization using Geoapify API**
- ✅ **Scalable & Event-Driven**

---

## 🏗️ Architecture Overview
1. 📂 **S3 Bucket** stores raw CSV manifests and optimized routes.
2. ⚡ **AWS Lambda** processes and optimizes routes.
3. 📊 **DynamoDB** stores delivery details and optimized routes.
4. 📡 **Geoapify API** finds the best delivery routes.
5. 🔔 **Future Enhancements**: CloudWatch logging, GitHub Actions for CI/CD.

---

## 🚀 Getting Started

### **1️⃣ Prerequisites**
- AWS Account with **S3, Lambda, and DynamoDB**
- Python 3 installed locally
- AWS CLI configured (`aws configure`)
