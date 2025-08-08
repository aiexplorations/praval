#!/usr/bin/env python3
"""
Example 006: Resilient Agent Systems
====================================

This example demonstrates how Praval agent systems can be designed
to handle errors gracefully, recover from failures, and maintain
system functionality even when individual agents fail.

Key Concepts:
- Error handling and recovery
- Agent fault tolerance
- Graceful degradation
- System resilience patterns
- Backup and redundancy strategies

Run: python examples/006_resilient_agents.py
"""

from praval import agent, chat, broadcast, start_agents
import random
import time


# Global state to simulate system conditions
system_state = {
    "error_rate": 0.3,  # 30% chance of errors for demonstration
    "backup_agents_active": True,
    "system_health": "normal"
}


@agent("primary_processor", responds_to=["process_request"])
def primary_processing_agent(spore):
    """
    I am the primary processor for requests. I may occasionally
    fail, demonstrating the need for resilient system design.
    """
    request = spore.knowledge.get("request", "unknown")
    request_id = spore.knowledge.get("request_id", "unknown")
    
    print(f"🔄 Primary Processor: Handling request {request_id} - '{request}'")
    
    # Simulate occasional failures for demonstration
    if random.random() < system_state["error_rate"]:
        error_msg = f"Primary processor encountered an error with request {request_id}"
        print(f"❌ Primary Processor: {error_msg}")
        
        # Broadcast error for recovery handling
        broadcast({
            "type": "processing_error",
            "request": request,
            "request_id": request_id,
            "error": error_msg,
            "failed_agent": "primary_processor"
        })
        
        return {"status": "error", "error": error_msg}
    
    # Normal processing
    result = chat(f"""
    Process this request: "{request}"
    
    Provide a thorough response that addresses the request effectively.
    Include processing details to show this came from the primary processor.
    """)
    
    print(f"✅ Primary Processor: Successfully processed {request_id}")
    
    broadcast({
        "type": "processing_complete",
        "request": request,
        "request_id": request_id,
        "result": result,
        "processor": "primary"
    })
    
    return {"status": "success", "result": result}


@agent("backup_processor", responds_to=["processing_error"])
def backup_processing_agent(spore):
    """
    I am a backup processor that handles requests when the
    primary processor fails, ensuring system resilience.
    """
    request = spore.knowledge.get("request")
    request_id = spore.knowledge.get("request_id")
    error = spore.knowledge.get("error")
    
    if not system_state["backup_agents_active"]:
        print(f"⚠️ Backup Processor: Backup systems are disabled")
        broadcast({
            "type": "backup_unavailable",
            "request_id": request_id,
            "error": "Backup systems unavailable"
        })
        return {"status": "backup_unavailable"}
    
    print(f"🔄 Backup Processor: Taking over request {request_id} after primary failure")
    print(f"   Original error: {error}")
    
    # Backup processing with simplified approach
    backup_result = chat(f"""
    As a backup processor, handle this request: "{request}"
    
    The primary processor failed, so provide a reliable, straightforward response.
    Include a note that this was handled by backup systems.
    """)
    
    print(f"✅ Backup Processor: Successfully handled {request_id} as backup")
    
    broadcast({
        "type": "processing_complete",
        "request": request,
        "request_id": request_id,
        "result": backup_result,
        "processor": "backup",
        "recovered_from_error": True
    })
    
    return {"status": "success", "result": backup_result, "backup_used": True}


@agent("health_monitor", responds_to=["processing_error", "backup_unavailable"])
def system_health_monitor(spore):
    """
    I monitor system health and can adjust system behavior
    to maintain resilience during difficult conditions.
    """
    message_type = spore.knowledge.get("type")
    request_id = spore.knowledge.get("request_id", "unknown")
    
    if message_type == "processing_error":
        print(f"🏥 Health Monitor: Detected primary system error for request {request_id}")
        
        # Check if we should adjust error rates or activate additional measures
        recent_errors = getattr(system_health_monitor, 'error_count', 0) + 1
        system_health_monitor.error_count = recent_errors
        
        if recent_errors >= 3:
            print(f"⚠️ Health Monitor: High error rate detected ({recent_errors} errors)")
            print(f"   Recommending system adjustments...")
            
            broadcast({
                "type": "health_alert",
                "alert_level": "high_error_rate",
                "error_count": recent_errors,
                "recommendation": "Consider reducing system load or investigating root cause"
            })
        
    elif message_type == "backup_unavailable":
        print(f"🚨 Health Monitor: CRITICAL - Both primary and backup systems unavailable for {request_id}")
        
        broadcast({
            "type": "health_alert",
            "alert_level": "critical",
            "issue": "No processing capability available",
            "recommendation": "Immediate intervention required"
        })
    
    return {"health_check": "monitoring_active"}


@agent("graceful_handler", responds_to=["backup_unavailable", "health_alert"])
def graceful_degradation_agent(spore):
    """
    I provide graceful degradation when normal processing
    systems are unavailable, ensuring users still get responses.
    """
    message_type = spore.knowledge.get("type")
    
    if message_type == "backup_unavailable":
        request_id = spore.knowledge.get("request_id")
        print(f"🛡️ Graceful Handler: Providing graceful degradation for request {request_id}")
        
        graceful_response = chat("""
        The system is currently experiencing technical difficulties.
        Provide a helpful message that:
        - Acknowledges the service interruption
        - Suggests alternative approaches or resources
        - Maintains a positive, professional tone
        - Indicates when service might be restored
        """)
        
        print(f"💬 Graceful Handler: {graceful_response}")
        
        broadcast({
            "type": "graceful_response_provided",
            "request_id": request_id,
            "response": graceful_response
        })
        
    elif message_type == "health_alert":
        alert_level = spore.knowledge.get("alert_level")
        recommendation = spore.knowledge.get("recommendation", "")
        
        print(f"🛡️ Graceful Handler: Responding to {alert_level} health alert")
        print(f"   Taking preventive measures: {recommendation}")
        
        if alert_level == "critical":
            # In a real system, this might trigger additional recovery procedures
            print("   Activating emergency protocols...")
    
    return {"graceful_degradation": "active"}


@agent("recovery_coordinator", responds_to=["health_alert"])
def system_recovery_coordinator(spore):
    """
    I coordinate system recovery efforts and can adapt
    system behavior to improve resilience.
    """
    alert_level = spore.knowledge.get("alert_level")
    error_count = spore.knowledge.get("error_count", 0)
    
    if alert_level == "high_error_rate":
        print(f"🔧 Recovery Coordinator: Initiating recovery procedures")
        print(f"   Detected {error_count} recent errors")
        
        # Simulate recovery actions
        recovery_actions = chat(f"""
        The system has experienced {error_count} recent errors.
        
        As a recovery coordinator, what steps should be taken to:
        - Reduce error rates
        - Improve system stability
        - Prevent cascading failures
        - Maintain service quality
        
        Provide specific, actionable recovery recommendations.
        """)
        
        print(f"🛠️ Recovery Coordinator: {recovery_actions}")
        
        # Reset error counter as part of recovery
        if hasattr(system_health_monitor, 'error_count'):
            system_health_monitor.error_count = 0
            print("🔄 Recovery Coordinator: Reset error tracking as part of recovery")
        
        broadcast({
            "type": "recovery_initiated",
            "actions": recovery_actions,
            "status": "system_stabilizing"
        })
    
    return {"recovery_status": "coordinating"}


def main():
    """Demonstrate resilient agent system behavior."""
    print("=" * 60)
    print("Example 006: Resilient Agent Systems")
    print("=" * 60)
    
    print("This system demonstrates resilience patterns:")
    print("- Primary processing with backup systems")
    print("- Error detection and recovery")
    print("- Health monitoring and alerts") 
    print("- Graceful degradation when systems fail")
    print("- System recovery coordination")
    print()
    
    # Test requests that will trigger various resilience patterns
    test_requests = [
        "Analyze market trends for technology stocks",
        "Create a summary of renewable energy options",
        "Explain the benefits of remote work",
        "Design a simple exercise routine",
        "Recommend books for learning programming",
        "Plan a weekend hiking trip"
    ]
    
    print(f"System configured with {system_state['error_rate']*100}% error rate for demonstration")
    print()
    
    for i, request in enumerate(test_requests, 1):
        print(f"=== Request {i}: {request} ===")
        
        # Start all resilience agents
        start_agents(
            primary_processing_agent,
            backup_processing_agent,
            system_health_monitor,
            graceful_degradation_agent,
            system_recovery_coordinator,
            initial_data={
                "type": "process_request",
                "request": request,
                "request_id": f"req_{i:03d}"
            }
        )
        
        print("\n" + "─" * 40 + "\n")
        
        # Brief pause to make the demonstration clearer
        time.sleep(0.5)
    
    print("Key Insights:")
    print("- Systems can gracefully handle individual agent failures")
    print("- Backup agents provide seamless error recovery")
    print("- Health monitoring enables proactive system management")
    print("- Graceful degradation maintains user experience during outages")
    print("- Recovery coordination helps systems return to normal operation")
    print("- Resilient design prevents single points of failure")


if __name__ == "__main__":
    main()