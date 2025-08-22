#!/usr/bin/env python3
"""
Unified Storage System Demo
===========================

This example demonstrates Praval's comprehensive storage capabilities:
- Multi-provider storage (PostgreSQL, Redis, S3, Qdrant, FileSystem)
- Storage decorators for agents
- Data references in spore communication
- Memory-storage integration
- Cross-storage queries and operations

Key Features Demonstrated:
- Automatic provider registration from environment
- Declarative storage access through decorators
- Data sharing between agents via storage references
- Smart storage selection based on data type
- Unified interface for memory and external storage

Run: python examples/unified_storage_demo.py

Prerequisites:
- Docker Compose running (for storage backends)
- Environment variables set for storage providers
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from praval import agent, chat, broadcast, start_agents
from praval.storage import (
    storage_enabled, get_storage_registry, get_data_manager,
    PostgreSQLProvider, RedisProvider, S3Provider, 
    FileSystemProvider, QdrantProvider
)


# Setup example data and environment
def setup_demo_environment():
    """Setup demo environment with storage providers."""
    print("🔧 Setting up demo environment...")
    
    # Create temporary directory for file storage
    temp_dir = Path(tempfile.mkdtemp()) / "praval_storage_demo"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Set environment variables for demo (in real usage, these would be set externally)
    demo_env = {
        "FILESYSTEM_BASE_PATH": str(temp_dir),
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "QDRANT_URL": "http://localhost:6333",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_DB": "praval",
        "POSTGRES_USER": "praval", 
        "POSTGRES_PASSWORD": "praval_secure_password",
        "S3_BUCKET_NAME": "praval-demo-bucket",
        "AWS_ACCESS_KEY_ID": "minioadmin",
        "AWS_SECRET_ACCESS_KEY": "minioadmin",
        "S3_ENDPOINT_URL": "http://localhost:9000"  # MinIO endpoint if available
    }
    
    for key, value in demo_env.items():
        os.environ[key] = value
    
    print(f"📁 Demo storage directory: {temp_dir}")
    return temp_dir


@storage_enabled(["filesystem"])
@agent("data_collector", responds_to=["collect_data"])
def data_collector_agent(spore, storage):
    """
    Collects and stores data across multiple storage backends.
    Demonstrates smart storage selection and data reference creation.
    """
    print(f"📊 Data Collector: Processing request from {spore.from_agent}")
    
    # Sample business data to collect
    customer_data = {
        "customers": [
            {"id": 1, "name": "Acme Corp", "revenue": 1500000, "industry": "Technology"},
            {"id": 2, "name": "Global Systems", "revenue": 2300000, "industry": "Finance"},
            {"id": 3, "name": "Innovation Labs", "revenue": 875000, "industry": "Research"}
        ]
    }
    
    sales_metrics = {
        "q1_2024": {"revenue": 2.5e6, "growth": 0.15, "customers": 150},
        "q2_2024": {"revenue": 2.8e6, "growth": 0.12, "customers": 175},
        "q3_2024": {"revenue": 3.1e6, "growth": 0.11, "customers": 190}
    }
    
    # Store customer data in filesystem (structured data)
    try:
        result = asyncio.run(storage.store("filesystem", "data/customers.json", customer_data))
        if result.success:
            customer_ref = result.data_reference.to_uri()
            print(f"✅ Stored customer data: {customer_ref}")
        else:
            print(f"❌ Failed to store customer data: {result.error}")
            return {"error": "Failed to store customer data"}
    except Exception as e:
        print(f"❌ Exception storing customer data: {e}")
        return {"error": f"Exception: {e}"}
    
    # Store sales metrics in Redis (fast access cache)
    try:
        result = asyncio.run(storage.store("redis", "sales:metrics:2024", sales_metrics))
        if result.success:
            sales_ref = result.data_reference.to_uri()
            print(f"✅ Cached sales metrics: {sales_ref}")
        else:
            print(f"❌ Failed to cache sales metrics: {result.error}")
    except Exception as e:
        print(f"❌ Exception caching sales metrics: {e}")
    
    # Create vector embeddings for semantic search (mock embeddings for demo)
    import random
    customer_embeddings = []
    for customer in customer_data["customers"]:
        embedding = [random.random() for _ in range(384)]  # Mock 384-dim embedding
        customer_embeddings.append({
            "id": f"customer_{customer['id']}",
            "vector": embedding,
            "payload": {
                "name": customer["name"],
                "industry": customer["industry"],
                "revenue": customer["revenue"]
            }
        })
    
    # Store embeddings in Qdrant for vector search
    try:
        result = asyncio.run(storage.store("qdrant", "customers", customer_embeddings))
        if result.success:
            vector_ref = result.data_reference.to_uri()
            print(f"✅ Stored customer vectors: {vector_ref}")
        else:
            print(f"❌ Failed to store vectors: {result.error}")
    except Exception as e:
        print(f"❌ Exception storing vectors: {e}")
    
    # Broadcast data collection completion with references
    broadcast({
        "type": "data_collected",
        "message": "Business data collection complete",
        "data_references": {
            "customers": customer_ref if 'customer_ref' in locals() else None,
            "sales_metrics": sales_ref if 'sales_ref' in locals() else None,
            "customer_vectors": vector_ref if 'vector_ref' in locals() else None
        },
        "stats": {
            "customers_count": len(customer_data["customers"]),
            "quarters_analyzed": len(sales_metrics)
        }
    })
    
    return {
        "status": "complete",
        "data_collected": ["customers", "sales_metrics", "embeddings"],
        "storage_backends": ["filesystem", "redis", "qdrant"]
    }


@storage_enabled(["redis", "filesystem", "qdrant"])
@agent("business_analyst", responds_to=["data_collected", "analyze_request"])
def business_analyst_agent(spore, storage):
    """
    Analyzes business data by retrieving from multiple storage backends.
    Demonstrates cross-storage operations and data reference resolution.
    """
    print(f"📈 Business Analyst: Analyzing data from {spore.from_agent}")
    
    analysis_results = {}
    
    # Resolve data references from spore
    if spore.has_data_references():
        print(f"🔗 Found {len(spore.data_references)} data references in spore")
        
        for ref_uri in spore.data_references:
            try:
                result = asyncio.run(storage.resolve_data_reference(ref_uri))
                if result.success:
                    print(f"✅ Resolved reference: {ref_uri}")
                    # Process resolved data based on reference type
                    if "customers" in ref_uri:
                        analysis_results["customer_analysis"] = analyze_customers(result.data)
                    elif "sales" in ref_uri:
                        analysis_results["sales_analysis"] = analyze_sales(result.data)
                else:
                    print(f"❌ Failed to resolve reference: {ref_uri}")
            except Exception as e:
                print(f"❌ Exception resolving reference {ref_uri}: {e}")
    
    # Also retrieve data directly from storage for demonstration
    try:
        # Get customer data from filesystem
        result = asyncio.run(storage.get("filesystem", "data/customers.json"))
        if result.success:
            print("✅ Retrieved customer data from filesystem")
            analysis_results["customer_analysis"] = analyze_customers(result.data)
        
        # Get sales metrics from Redis cache
        result = asyncio.run(storage.get("redis", "sales:metrics:2024"))
        if result.success:
            print("✅ Retrieved sales metrics from Redis")
            analysis_results["sales_analysis"] = analyze_sales(result.data)
        
        # Perform vector search on customer data
        if "customer_analysis" in analysis_results:
            # Mock query vector for high-revenue customer search
            query_vector = [random.random() for _ in range(384)]
            result = asyncio.run(storage.query(
                "qdrant", "customers", "search",
                vector=query_vector, limit=3, with_payload=True
            ))
            if result.success:
                print("✅ Performed vector search on customer data")
                analysis_results["similar_customers"] = result.data
    
    except Exception as e:
        print(f"❌ Exception during analysis: {e}")
        analysis_results["error"] = str(e)
    
    # Generate comprehensive business report
    report = generate_business_report(analysis_results)
    
    # Store analysis report in filesystem
    try:
        result = asyncio.run(storage.store(
            "filesystem", "reports/business_analysis.md", report
        ))
        if result.success:
            report_ref = result.data_reference.to_uri()
            print(f"✅ Stored analysis report: {report_ref}")
        
            # Broadcast analysis completion
            broadcast({
                "type": "analysis_complete", 
                "message": "Business analysis completed",
                "report_reference": report_ref,
                "insights": analysis_results.get("summary", {})
            })
    except Exception as e:
        print(f"❌ Failed to store report: {e}")
    
    return {
        "status": "analysis_complete",
        "results": analysis_results,
        "report_stored": "reports/business_analysis.md"
    }


def analyze_customers(customer_data):
    """Analyze customer data and extract insights."""
    if not customer_data or "customers" not in customer_data:
        return {"error": "Invalid customer data"}
    
    customers = customer_data["customers"]
    total_revenue = sum(c["revenue"] for c in customers)
    avg_revenue = total_revenue / len(customers)
    
    industries = {}
    for customer in customers:
        industry = customer["industry"]
        industries[industry] = industries.get(industry, 0) + 1
    
    return {
        "total_customers": len(customers),
        "total_revenue": total_revenue,
        "average_revenue": avg_revenue,
        "industries": industries,
        "top_customer": max(customers, key=lambda c: c["revenue"])
    }


def analyze_sales(sales_data):
    """Analyze sales metrics and identify trends."""
    if not sales_data:
        return {"error": "Invalid sales data"}
    
    quarters = list(sales_data.keys())
    revenues = [sales_data[q]["revenue"] for q in quarters]
    growth_rates = [sales_data[q]["growth"] for q in quarters]
    
    return {
        "quarters_analyzed": len(quarters),
        "total_revenue": sum(revenues),
        "average_growth": sum(growth_rates) / len(growth_rates),
        "revenue_trend": "increasing" if revenues[-1] > revenues[0] else "decreasing",
        "best_quarter": max(quarters, key=lambda q: sales_data[q]["revenue"])
    }


def generate_business_report(analysis_results):
    """Generate a comprehensive business report in Markdown format."""
    report = "# Business Analysis Report\n\n"
    report += f"Generated on: {os.popen('date').read().strip()}\n\n"
    
    if "customer_analysis" in analysis_results:
        ca = analysis_results["customer_analysis"]
        report += "## Customer Analysis\n\n"
        report += f"- **Total Customers**: {ca.get('total_customers', 'N/A')}\n"
        report += f"- **Total Revenue**: ${ca.get('total_revenue', 0):,.2f}\n"
        report += f"- **Average Revenue**: ${ca.get('average_revenue', 0):,.2f}\n"
        
        if "industries" in ca:
            report += "\n### Industry Distribution\n"
            for industry, count in ca["industries"].items():
                report += f"- {industry}: {count} customers\n"
        
        if "top_customer" in ca:
            top = ca["top_customer"]
            report += f"\n### Top Customer\n"
            report += f"- **Name**: {top['name']}\n"
            report += f"- **Revenue**: ${top['revenue']:,.2f}\n"
            report += f"- **Industry**: {top['industry']}\n"
    
    if "sales_analysis" in analysis_results:
        sa = analysis_results["sales_analysis"]
        report += "\n## Sales Analysis\n\n"
        report += f"- **Quarters Analyzed**: {sa.get('quarters_analyzed', 'N/A')}\n"
        report += f"- **Total Revenue**: ${sa.get('total_revenue', 0):,.2f}\n"
        report += f"- **Average Growth Rate**: {sa.get('average_growth', 0):.1%}\n"
        report += f"- **Revenue Trend**: {sa.get('revenue_trend', 'N/A')}\n"
        report += f"- **Best Quarter**: {sa.get('best_quarter', 'N/A')}\n"
    
    if "similar_customers" in analysis_results:
        report += "\n## Vector Search Results\n\n"
        report += "Similar customers found through semantic search:\n"
        for i, customer in enumerate(analysis_results["similar_customers"], 1):
            payload = customer.get("payload", {})
            score = customer.get("score", 0)
            report += f"{i}. **{payload.get('name', 'Unknown')}** (similarity: {score:.3f})\n"
            report += f"   - Industry: {payload.get('industry', 'N/A')}\n"
            report += f"   - Revenue: ${payload.get('revenue', 0):,.2f}\n"
    
    report += "\n---\n"
    report += "*Report generated by Praval Multi-Agent Framework with Unified Storage*\n"
    
    return report


@storage_enabled(["filesystem"])
@agent("report_viewer", responds_to=["analysis_complete"])
def report_viewer_agent(spore, storage):
    """
    Views and summarizes the generated business report.
    Demonstrates data reference resolution and file operations.
    """
    print(f"📄 Report Viewer: Processing report from {spore.from_agent}")
    
    # Get report reference from spore
    report_reference = spore.knowledge.get("report_reference")
    
    if report_reference:
        try:
            # Resolve the data reference to get the actual report
            result = asyncio.run(storage.resolve_data_reference(report_reference))
            
            if result.success:
                report_content = result.data
                print("✅ Successfully retrieved business report")
                print("\n" + "="*60)
                print("BUSINESS ANALYSIS REPORT")
                print("="*60)
                print(report_content)
                print("="*60 + "\n")
                
                # Extract key insights using AI
                insights = chat(f"Summarize the key business insights from this report in 3 bullet points:\n\n{report_content}")
                
                print("🔍 Key Insights:")
                print(insights)
                
                return {
                    "status": "report_viewed",
                    "report_length": len(report_content),
                    "insights": insights
                }
            else:
                print(f"❌ Failed to retrieve report: {result.error}")
                return {"error": "Failed to retrieve report"}
        
        except Exception as e:
            print(f"❌ Exception viewing report: {e}")
            return {"error": str(e)}
    else:
        print("❌ No report reference found in spore")
        return {"error": "No report reference provided"}


async def demo_storage_registry():
    """Demonstrate storage registry capabilities."""
    print("\n🗄️  Storage Registry Demo")
    print("-" * 40)
    
    registry = get_storage_registry()
    
    # Show registered providers
    providers = registry.list_providers()
    print(f"📋 Registered Providers: {providers}")
    
    # Show providers by type
    from praval.storage.base_provider import StorageType
    for storage_type in StorageType:
        type_providers = registry.get_providers_by_type(storage_type)
        if type_providers:
            print(f"📁 {storage_type.value}: {type_providers}")
    
    # Perform health checks
    print("\n🏥 Health Check Results:")
    health_results = await registry.health_check_all()
    for provider_name, health in health_results.items():
        status_emoji = "✅" if health["status"] == "healthy" else "❌"
        print(f"{status_emoji} {provider_name}: {health['status']}")


async def demo_smart_storage():
    """Demonstrate smart storage selection."""
    print("\n🧠 Smart Storage Demo")
    print("-" * 30)
    
    data_manager = get_data_manager()
    
    # Different types of data for smart selection
    test_data = [
        ("Simple text", "Hello, World!"),
        ("Structured data", {"name": "John", "age": 30, "city": "New York"}),
        ("Large JSON", {"data": [{"id": i, "value": f"item_{i}"} for i in range(100)]}),
        ("Vector data", {"vector": [0.1, 0.2, 0.3], "metadata": {"type": "embedding"}})
    ]
    
    for data_type, data in test_data:
        try:
            result = await data_manager.smart_store(data)
            if result.success:
                provider_used = result.data_reference.provider if result.data_reference else "unknown"
                print(f"✅ {data_type} → {provider_used}")
            else:
                print(f"❌ {data_type} → Failed: {result.error}")
        except Exception as e:
            print(f"❌ {data_type} → Exception: {e}")


async def main():
    """Main demo function."""
    print("🚀 Praval Unified Storage System Demo")
    print("=" * 50)
    
    # Setup demo environment
    temp_dir = setup_demo_environment()
    
    try:
        # Demo storage registry
        await demo_storage_registry()
        
        # Demo smart storage
        await demo_smart_storage()
        
        print(f"\n🤖 Starting Multi-Agent Storage Demo")
        print("-" * 40)
        
        # Start the agent system
        result = start_agents(
            data_collector_agent,
            business_analyst_agent, 
            report_viewer_agent,
            initial_data={"type": "start_analysis"}
        )
        
        print(f"\n✅ Demo completed successfully!")
        print(f"📁 Demo files stored in: {temp_dir}")
        print("\n🎯 Key Features Demonstrated:")
        print("   • Multi-provider storage (FileSystem, Redis, Qdrant)")
        print("   • Storage decorators for agents") 
        print("   • Data references in spore communication")
        print("   • Cross-storage operations and queries")
        print("   • Smart storage selection")
        print("   • Unified memory-storage interface")
        
        return result
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        raise
    finally:
        # Cleanup
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"🧹 Cleaned up demo directory: {temp_dir}")
        except Exception:
            pass


if __name__ == "__main__":
    # Import for demo - in production these would be set externally
    import random
    
    # Run the demo
    asyncio.run(main())