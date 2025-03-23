Delivery Optimizer Readme

🚀 Delivery Manifest Optimizer

Welcome to my first AWS-powered project: Delivery Manifest Optimizer! 🎉

This project automates the optimization of delivery routes, eliminating the tedious and time-consuming task of manually entering routes into tools like Circuit Route Planner. Originally developed to solve real-world logistics challenges for Inrout, it streamlines route planning, driver assignments, and estimated arrival times (ETA) calculations using AWS cloud infrastructure.

🛠️ What Does It Do?

✅ Automatically processes delivery manifests uploaded as CSV files.

✅ Assigns drivers based on postcode prefixes.

✅ Optimizes delivery routes for maximum efficiency.

✅ Provides accurate Estimated Arrival Times (ETAs).

✅ Stores and manages data efficiently with AWS DynamoDB.

✅ Exposes ETAs via an API Gateway for easy integration with client apps.

                   ┌───────────────────────────┐
                   │ CSV Delivery Manifest     │
                   │ Uploaded to AWS S3 Bucket │
                   └─────────────┬─────────────┘
                                 │ Trigger (S3 Event)
                                 ▼
                   ┌───────────────────────────┐
                   │ AWS Lambda Function       │
                   │ "ProcessDeliveryCSV"      │
                   └─────────────┬─────────────┘
                                 │
                                 ▼
                   ┌───────────────────────────┐
                   │ DynamoDB Table            │
                   │ "DeliveryManagement"      │
                   └─────────────┬─────────────┘
                                 │
                                 ▼
                   ┌───────────────────────────┐
                   │ Lambda Function           │
                   │ "OptimizeDriverRoutes"    │
                   └─────────────┬─────────────┘
                                 │
                                 ▼
                   ┌───────────────────────────┐
                   │ Optimized Routes CSV      │
                   │ (stored back in S3 bucket)│
                   └─────────────┬─────────────┘
                                 │ Trigger (S3 Event)
                                 ▼
                   ┌───────────────────────────┐
                   │ Lambda Function           │
                   │ "UpdateDriverETA"         │
                   └─────────────┬─────────────┘
                                 │
                                 ▼
                   ┌───────────────────────────┐
                   │ DynamoDB Table            │
                   │ "DriverLocations"         │
                   └─────────────┬─────────────┘
                                 │
                                 ▼
                   ┌───────────────────────────┐
                   │ API Gateway Endpoint      │
                   │ "getDriverETA"            │
                   └─────────────┬─────────────┘
                                 │
                                 ▼
                   ┌───────────────────────────┐
                   │ User/Client Application   │
                   │ (Fetch Driver ETA Data)   │
                   └───────────────────────────┘
🌟 Tech Stack AWS Lambda: Serverless compute to handle manifest processing and route optimization.

Amazon DynamoDB: NoSQL database to store delivery and driver information.

Amazon S3: Storage for delivery manifests and optimized routes.

AWS API Gateway: Provides secure, scalable API endpoints.

Terraform: Infrastructure as Code (IaC) for streamlined deployment and management.

📌 Project Flow CSV files are uploaded to an S3 bucket.

S3 event triggers Lambda function to process CSV.

Lambda assigns drivers and updates DynamoDB.

Lambda triggers route optimization, saving optimized routes back to S3.

Another Lambda updates DynamoDB with optimized ETAs.

Client applications access ETAs through API Gateway endpoints.

🚧 Upcoming Improvements 📍 Live tracking functionality and real-time driver location updates.

📈 Enhanced observability and monitoring (CloudWatch and X-Ray).

⚙️ CI/CD pipeline integration with GitHub Actions.

📱 Improved client-facing interface and mobile compatibility.

📚 Learning Journey As I'm currently studying for my AWS Solutions Architect Associate Certification (SAA-C03), this project is a practical way to apply and strengthen my cloud architecture skills. I'd greatly appreciate feedback or suggestions from experienced cloud engineers or AWS enthusiasts—feel free to point out areas of improvement!

🤝 Let's Collaborate! I'm open to collaborations, discussions, and knowledge sharing. If you have ideas, suggestions, or improvements, let's connect!

Let's build something great together!`)