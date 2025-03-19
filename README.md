# Delivery Manifest Optimizer 🚚

**A serverless AWS-based tool for optimizing last-mile delivery routes.**  
This project processes delivery manifests (CSV files), optimizes driver routes using **Google Route API**, and exports an optimized CSV for each driver per postcode. This emulates Circuit Route Planner's application on AWS using the free tier to provide part of the service last mile delivery companies pay £200 a month for. 

---

## 📌 Features
- ✅ **AWS Serverless Architecture** (S3, Lambda, DynamoDB)
- ✅ **Automated CSV Processing** when a file is uploaded to S3
- ✅ **Route Optimization using Google Maps API**
- ✅ **Scalable & Event-Driven**

---

## 🏗️ Architecture Overview
✅ Automated Delivery Manifest Processing – Upload a CSV file to S3, and the system automatically processes and stores the data in DynamoDB.
✅ Driver Assignment – Assigns drivers dynamically based on postcode prefixes.
✅ Route Optimization – Calls an external API (Google Routes API) to optimize delivery routes.
✅ ETA Calculation – Stores estimated arrival times for each driver.
✅ Event-Driven Architecture – Uses AWS Lambda and API Gateway for a fully serverless setup.
✅ Infrastructure as Code (Terraform) – Easily deploy and manage infrastructure.
✅ Scalability & Cost Efficiency – Uses DynamoDB with on-demand billing for cost efficiency.

🛠️ **Tech Stack**
🔹 **AWS Lambda** – Event-driven function for processing manifests.
🔹 **AWS S3** – Storage for incoming and processed CSV files.
🔹 **AWS DynamoDB** – NoSQL database for storing deliveries and driver ETAs.
🔹 **AWS API Gateway** – Provides an API endpoint for fetching ETAs.
🔹 **Terraform** (Planned) – Infrastructure as Code for easy deployment.
🔹 **Google Maps API** – Used for optimizing delivery routes.
🔹 **GitHub Actions** (Planned) – Future CI/CD pipeline integration.

🚀 **How It Works**
1️⃣ Upload a delivery manifest to the S3 incoming/ folder.
2️⃣ Lambda function automatically processes the file and stores deliveries in DynamoDB.
3️⃣ Route optimization is triggered, calculating the most efficient paths.
4️⃣ Driver ETAs are stored in a separate table for tracking.
5️⃣ Get delivery ETAs via API Gateway (planned feature for live tracking).

📌 What's Next?
🔹 Real-time driver location updates (planned).
🔹 Integration with CI/CD (GitHub Actions).
🔹 Further optimizations for route planning.
---

**👥 Contributing**
Feel free to fork this repository and open pull requests with improvements! This is my first project and is bound to have alot of errors so any help is much appreciated. 🚀

**📬 Questions? Suggestions? Open an issue or reach out.**

