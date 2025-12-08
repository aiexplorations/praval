#!/usr/bin/env python3
"""
Example 007: Adaptive Agent Systems
===================================

This example demonstrates how agent systems can adapt and evolve
their behavior based on feedback, changing conditions, and learned
patterns. Agents modify their approaches, spawn new capabilities,
and optimize their performance over time.

Key Concepts:
- Behavioral adaptation based on feedback
- Performance optimization through learning
- Dynamic system reconfiguration
- Emergent capability development
- Self-improving agent networks

Run: python examples/007_adaptive_agent_systems.py
"""

from praval import agent, chat, broadcast, start_agents, get_reef
import random
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Global system state for tracking adaptation
adaptation_state = {
    "performance_metrics": defaultdict(list),
    "behavioral_patterns": {},
    "optimization_history": [],
    "active_strategies": set(),
    "environment_conditions": "normal"
}


@agent("adaptive_processor", responds_to=["adaptive_task", "strategy_update"])
def adaptive_processing_agent(spore):
    """
    I am an adaptive processor that modifies my approach
    based on performance feedback and changing conditions.
    """
    message_type = spore.knowledge.get("type")
    
    if message_type == "strategy_update":
        strategy = spore.knowledge.get("new_strategy")
        performance_data = spore.knowledge.get("performance_data", {})
        
        print(f"🔄 Adaptive Processor: Updating strategy based on feedback")
        print(f"   New strategy: {strategy}")
        
        adaptation_state["active_strategies"].add(strategy)
        
        broadcast({
            "type": "strategy_adopted",
            "strategy": strategy,
            "adopter": "adaptive_processor"
        })
        
        return {"strategy_updated": True}
    
    elif message_type == "adaptive_task":
        task = spore.knowledge.get("task")
        task_id = spore.knowledge.get("task_id", "unknown")
        conditions = spore.knowledge.get("conditions", "normal")
        
        # Adapt approach based on current strategies and conditions
        current_strategies = list(adaptation_state["active_strategies"])
        past_performance = adaptation_state["performance_metrics"].get("adaptive_processor", [])
        
        if past_performance:
            avg_performance = sum(past_performance[-5:]) / min(5, len(past_performance))
            performance_context = f"Recent average performance: {avg_performance:.2f}/10"
        else:
            performance_context = "No prior performance data"
        
        print(f"🧠 Adaptive Processor: Handling task {task_id} under '{conditions}' conditions")
        print(f"   Active strategies: {current_strategies}")
        print(f"   {performance_context}")
        
        adaptive_response = chat(f"""
        Task: "{task}"
        Conditions: {conditions}
        Active strategies: {current_strategies}
        Performance context: {performance_context}
        
        Adapt your processing approach based on:
        - Current environmental conditions
        - Lessons learned from past performance
        - Available optimization strategies
        
        Provide both the task result and notes on your adaptive approach.
        """)
        
        print(f"✅ Adaptive Processor: {adaptive_response}")
        
        # Simulate performance measurement
        performance_score = random.uniform(6.0, 10.0)  # Bias toward improvement over time
        adaptation_state["performance_metrics"]["adaptive_processor"].append(performance_score)
        
        broadcast({
            "type": "task_completed",
            "task": task,
            "task_id": task_id,
            "result": adaptive_response,
            "performance_score": performance_score,
            "conditions": conditions,
            "strategies_used": current_strategies
        })
        
        return {"result": adaptive_response, "performance": performance_score}


@agent("performance_analyzer", responds_to=["task_completed"])
def performance_analysis_agent(spore):
    """
    I analyze performance patterns and recommend adaptations
    to improve system effectiveness over time.
    """
    task_id = spore.knowledge.get("task_id")
    performance_score = spore.knowledge.get("performance_score", 0)
    conditions = spore.knowledge.get("conditions", "normal")
    strategies_used = spore.knowledge.get("strategies_used", [])
    
    print(f"📊 Performance Analyzer: Analyzing task {task_id}")
    print(f"   Performance: {performance_score:.2f}/10 under '{conditions}' conditions")
    
    # Analyze trends and patterns
    all_scores = adaptation_state["performance_metrics"]["adaptive_processor"]
    
    if len(all_scores) >= 3:
        recent_trend = sum(all_scores[-3:]) / 3 - sum(all_scores[-6:-3]) / 3 if len(all_scores) >= 6 else 0
        trend_direction = "improving" if recent_trend > 0.2 else "declining" if recent_trend < -0.2 else "stable"
        
        print(f"📈 Performance Analyzer: Performance trend is {trend_direction} (Δ{recent_trend:+.2f})")
        
        # Recommend adaptations based on analysis
        if trend_direction == "declining" or performance_score < 7.0:
            analysis_result = chat(f"""
            Performance is {trend_direction} with score {performance_score:.2f}/10.
            Conditions: {conditions}
            Current strategies: {strategies_used}
            
            As a performance analyst, recommend specific adaptations:
            - What behavioral changes could improve performance?
            - Should we try new strategies or optimize existing ones?
            - How should we adapt to current conditions?
            
            Provide concrete, actionable recommendations.
            """)
            
            print(f"💡 Performance Analyzer: {analysis_result}")
            
            # Trigger adaptation
            broadcast({
                "type": "adaptation_needed",
                "analysis": analysis_result,
                "current_performance": performance_score,
                "trend": trend_direction,
                "conditions": conditions
            })
            
        else:
            print(f"✅ Performance Analyzer: Performance is satisfactory - maintaining current approach")
    
    # Store pattern data
    pattern_key = f"{conditions}_{'-'.join(sorted(strategies_used))}"
    if pattern_key not in adaptation_state["behavioral_patterns"]:
        adaptation_state["behavioral_patterns"][pattern_key] = []
    adaptation_state["behavioral_patterns"][pattern_key].append(performance_score)
    
    return {"analysis_complete": True, "performance": performance_score}


@agent("adaptation_coordinator", responds_to=["adaptation_needed"])
def system_adaptation_coordinator(spore):
    """
    I coordinate system-wide adaptations by developing new
    strategies and coordinating behavioral changes.
    """
    analysis = spore.knowledge.get("analysis")
    current_performance = spore.knowledge.get("current_performance", 0)
    trend = spore.knowledge.get("trend", "unknown")
    conditions = spore.knowledge.get("conditions", "normal")
    
    print(f"🎯 Adaptation Coordinator: Coordinating system adaptation")
    print(f"   Performance: {current_performance:.2f}/10, Trend: {trend}")
    
    # Develop new strategies based on conditions and analysis
    new_strategy = chat(f"""
    System needs adaptation due to {trend} performance ({current_performance:.2f}/10).
    Current conditions: {conditions}
    Analysis: {analysis}
    
    Develop a specific new strategy that could improve performance:
    - Be concrete and actionable
    - Address the identified performance issues
    - Consider the current environmental conditions
    - Suggest specific behavioral modifications
    
    Return just the strategy name and brief description.
    """)
    
    print(f"🔧 Adaptation Coordinator: Developed new strategy: {new_strategy}")
    
    # Record optimization attempt
    adaptation_state["optimization_history"].append({
        "timestamp": time.time(),
        "trigger": f"{trend}_performance",
        "strategy": new_strategy,
        "conditions": conditions
    })
    
    # Broadcast new strategy for adoption
    broadcast({
        "type": "strategy_update",
        "new_strategy": new_strategy,
        "performance_data": {
            "current": current_performance,
            "trend": trend
        },
        "conditions": conditions
    })
    
    return {"new_strategy": new_strategy}


@agent("capability_evolver", responds_to=["strategy_adopted"])
def capability_evolution_agent(spore):
    """
    I help evolve new capabilities by observing successful
    strategies and spawning specialized agents when needed.
    """
    strategy = spore.knowledge.get("strategy")
    adopter = spore.knowledge.get("adopter")
    
    print(f"🧬 Capability Evolver: Observing strategy adoption: '{strategy}'")
    
    # Check if this strategy suggests need for new capabilities
    capability_analysis = chat(f"""
    A new strategy was adopted: "{strategy}"
    
    Analyze if this suggests the need for:
    - New specialized agent types
    - Enhanced existing capabilities  
    - Novel collaboration patterns
    - Emergent system behaviors
    
    Should the system evolve new capabilities to support this strategy?
    If yes, describe what new agent type or capability would be valuable.
    """)
    
    print(f"🔬 Capability Evolver: {capability_analysis}")
    
    # Simulate capability evolution decision
    if "new" in capability_analysis.lower() and "agent" in capability_analysis.lower():
        print(f"🆕 Capability Evolver: Recommending new capability development")
        
        broadcast({
            "type": "capability_evolution",
            "recommendation": capability_analysis,
            "trigger_strategy": strategy
        })
    
    return {"evolution_analysis": capability_analysis}


@agent("system_observer", responds_to=["capability_evolution"])
def emergent_behavior_observer(spore):
    """
    I observe emergent behaviors and patterns that arise
    from the adaptive agent system over time.
    """
    recommendation = spore.knowledge.get("recommendation")
    trigger_strategy = spore.knowledge.get("trigger_strategy")
    
    print(f"👁️ System Observer: Observing emergent behavior")
    print(f"   Triggered by strategy: {trigger_strategy}")
    
    # Analyze system evolution
    total_adaptations = len(adaptation_state["optimization_history"])
    active_strategies = len(adaptation_state["active_strategies"])
    pattern_diversity = len(adaptation_state["behavioral_patterns"])
    
    emergence_analysis = chat(f"""
    System evolution observations:
    - Total adaptations: {total_adaptations}
    - Active strategies: {active_strategies}
    - Behavioral patterns discovered: {pattern_diversity}
    
    Latest recommendation: {recommendation}
    
    What emergent behaviors or patterns do you observe in this adaptive system?
    How is the system evolving beyond its initial design?
    What does this suggest about the nature of adaptive agent systems?
    """)
    
    print(f"🌱 System Observer: {emergence_analysis}")
    
    return {"emergence_analysis": emergence_analysis}


def main():
    """Demonstrate adaptive agent system behavior."""
    print("=" * 60)
    print("Example 007: Adaptive Agent Systems")
    print("=" * 60)
    
    print("This system demonstrates adaptive behaviors:")
    print("- Performance-based behavioral adaptation")
    print("- Strategy development and optimization")
    print("- System-wide coordination of changes")
    print("- Capability evolution over time")
    print("- Emergent behavior observation")
    print()
    
    # Simulate changing conditions to trigger adaptations
    task_scenarios = [
        {"conditions": "normal", "tasks": 3},
        {"conditions": "high_complexity", "tasks": 2},
        {"conditions": "time_pressure", "tasks": 3},
        {"conditions": "resource_constrained", "tasks": 2},
        {"conditions": "optimal", "tasks": 2}
    ]
    
    task_counter = 1
    
    for scenario in task_scenarios:
        conditions = scenario["conditions"]
        num_tasks = scenario["tasks"]
        
        print(f"=== Scenario: {conditions.upper()} CONDITIONS ===")
        adaptation_state["environment_conditions"] = conditions
        
        for i in range(num_tasks):
            task_id = f"task_{task_counter:03d}"
            
            # Generate task appropriate for conditions
            # Using predefined tasks instead of LLM generation for standalone demo
            task_templates = {
                "normal": [
                    "Process customer order #12345 with standard 2-day shipping",
                    "Analyze quarterly sales data for product recommendations", 
                    "Update inventory levels for warehouse management",
                    "Generate monthly financial report for stakeholders"
                ],
                "high_load": [
                    "Handle surge in customer orders during flash sale",
                    "Process 10,000 concurrent user requests efficiently",
                    "Scale system resources to meet peak demand",
                    "Optimize database queries for high traffic"
                ],
                "error_prone": [
                    "Recover from database connection timeout",
                    "Handle corrupted data file with graceful fallback",
                    "Process incomplete customer information carefully",
                    "Manage network connectivity issues during operation"
                ]
            }
            
            tasks = task_templates.get(conditions, task_templates["normal"])
            task_description = tasks[i % len(tasks)]
            
            print(f"\n--- Task {task_counter}: {task_description} ---")
            
            start_agents(
                adaptive_processing_agent,
                performance_analysis_agent,
                system_adaptation_coordinator,
                capability_evolution_agent,
                emergent_behavior_observer,
                initial_data={
                    "type": "adaptive_task",
                    "task": task_description,
                    "task_id": task_id,
                    "conditions": conditions
                }
            )

            # Wait for agents to complete
            get_reef().wait_for_completion()

            task_counter += 1

        print(f"\n--- End of {conditions} scenario ---")
        print(f"Active strategies: {len(adaptation_state['active_strategies'])}")
        print(f"Optimization attempts: {len(adaptation_state['optimization_history'])}")
        print()

    # Shutdown reef after all iterations
    get_reef().shutdown()

    print("=" * 60)
    print("SYSTEM EVOLUTION SUMMARY")
    print("=" * 60)
    print(f"Total performance measurements: {len(adaptation_state['performance_metrics']['adaptive_processor'])}")
    print(f"Strategies developed: {len(adaptation_state['active_strategies'])}")
    print(f"Behavioral patterns identified: {len(adaptation_state['behavioral_patterns'])}")
    print(f"Optimization cycles completed: {len(adaptation_state['optimization_history'])}")
    
    if adaptation_state['performance_metrics']['adaptive_processor']:
        scores = adaptation_state['performance_metrics']['adaptive_processor']
        initial_avg = sum(scores[:3]) / min(3, len(scores))
        final_avg = sum(scores[-3:]) / min(3, len(scores))
        improvement = final_avg - initial_avg
        print(f"Performance improvement: {improvement:+.2f} points")
    
    print()
    print("Key Insights:")
    print("- Systems can learn and improve from experience")
    print("- Performance feedback drives behavioral adaptation")
    print("- Strategies evolve to match environmental conditions")
    print("- New capabilities emerge from successful patterns")
    print("- Adaptive systems exhibit emergent intelligence")
    print("- Self-improvement happens without external programming")


if __name__ == "__main__":
    main()