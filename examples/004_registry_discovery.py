#!/usr/bin/env python3
"""
Example 004: Registry-Based Discovery
=====================================

This example demonstrates how agents can discover and coordinate with
each other through the registry system, enabling loose coupling and
dynamic composition.

Key Concepts:
- Agent registry and discovery
- Self-organizing collaboration
- Dynamic capability discovery
- Loose coupling between agents
- Service-oriented agent architecture

Run: python examples/004_registry_discovery.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from praval import agent, broadcast, start_agents, get_registry, get_reef


@agent("coordinator")
def task_coordinator(spore):
    """
    I coordinate complex tasks by discovering available specialists
    and orchestrating their collaboration.
    """
    task = spore.knowledge.get("task", "Create a learning plan")
    
    print(f"📋 Coordinator: Received task - '{task}'")
    
    # Discover available agents
    registry = get_registry()
    available_agents = registry.list_agents()
    
    print(f"🔍 Coordinator: Found {len(available_agents)} available agents:")
    for agent_info in available_agents:
        if agent_info["name"] != "coordinator":  # Don't include self
            print(f"   - {agent_info['name']}")
    
    # Determine what type of help is needed with fallback
    try:
        from praval import chat
        task_analysis = chat(f"""
        For the task: "{task}"
        
        What types of specialists would be most helpful? Consider:
        - Research specialists (for gathering information)
        - Planning specialists (for structuring approaches)
        - Creative specialists (for innovative ideas)
        - Quality specialists (for evaluation and refinement)
        
        Return a brief analysis of what specialist capabilities are needed.
        """)
    except Exception:
        # Fallback analysis based on task type
        if "plan" in task.lower() or "design" in task.lower():
            task_analysis = "This task requires research specialists for background information, planning specialists for structure, and quality specialists for review."
        elif "create" in task.lower() or "develop" in task.lower():
            task_analysis = "This task needs creative specialists for ideation, research specialists for context, and planning specialists for implementation."
        else:
            task_analysis = "This task would benefit from research specialists, planning specialists, and quality review specialists."
    
    print(f"🎯 Coordinator: Task needs - {task_analysis}")
    
    # Broadcast request for relevant specialists
    broadcast({
        "type": "seeking_specialists",
        "task": task,
        "task_analysis": task_analysis,
        "coordinator": "coordinator"
    })
    
    return {"task_analysis": task_analysis}


@agent("researcher", responds_to=["seeking_specialists"])
def research_specialist(spore):
    """
    I specialize in researching topics and gathering relevant
    information to support decision-making.
    """
    task = spore.knowledge.get("task")
    analysis = spore.knowledge.get("task_analysis", "")
    
    # Check if research capabilities are needed
    if "research" in analysis.lower() or "information" in analysis.lower():
        print(f"📚 Researcher: I can help with research for '{task}'")
        
        # Research with fallback
        try:
            from praval import chat
            research = chat(f"""
            For the task "{task}", provide key research insights:
            - Important background information
            - Best practices or proven approaches
            - Resources or examples to consider
            - Potential challenges to be aware of
            """)
        except Exception:
            # Fallback research
            research = f"""Research insights for "{task}":
            
            - Background: This type of task typically requires careful planning, stakeholder consideration, and iterative implementation.
            - Best practices: Start small, gather feedback early, involve key stakeholders, and maintain clear communication.
            - Resources: Consider existing frameworks, industry standards, and successful case studies in similar domains.
            - Challenges: Resource constraints, stakeholder alignment, timeline pressures, and maintaining quality standards."""
        
        print(f"📖 Researcher: {research}")
        
        broadcast({
            "type": "research_contribution",
            "task": task,
            "research": research,
            "from": "researcher"
        })
        
        return {"research": research}
    else:
        print(f"📚 Researcher: Task doesn't seem to need my research skills")
        return {"status": "not_applicable"}


@agent("planner", responds_to=["seeking_specialists", "research_contribution"])
def planning_specialist(spore):
    """
    I specialize in creating structured plans and organizing
    complex tasks into manageable steps.
    """
    task = spore.knowledge.get("task")
    message_type = spore.knowledge.get("type")
    
    if message_type == "seeking_specialists":
        analysis = spore.knowledge.get("task_analysis", "")
        if "planning" in analysis.lower() or "structure" in analysis.lower():
            print(f"📋 Planner: I can help with planning for '{task}'")
            return {"status": "available"}
    
    elif message_type == "research_contribution":
        research = spore.knowledge.get("research", "")
        
        # Planning with fallback
        try:
            from praval import chat
            plan = chat(f"""
            Based on this research for "{task}":
            {research}
            
            Create a structured plan with:
            - Clear objectives
            - 4-6 main steps or phases  
            - Key considerations for each step
            - Success criteria
            """)
        except Exception:
            # Fallback plan
            plan = f"""Structured Plan for "{task}":
            
            Objectives: Deliver a comprehensive solution that meets stakeholder needs and can be implemented effectively.
            
            Phase 1: Discovery and Research
            - Gather requirements and constraints
            - Identify stakeholders and resources
            
            Phase 2: Design and Planning
            - Create detailed specifications
            - Develop implementation timeline
            
            Phase 3: Implementation
            - Execute plan in manageable increments
            - Monitor progress and adjust as needed
            
            Phase 4: Review and Optimization
            - Evaluate results against objectives
            - Implement improvements and lessons learned
            
            Success Criteria: Clear deliverables, stakeholder satisfaction, and sustainable outcomes."""
        
        print(f"📅 Planner: {plan}")
        
        broadcast({
            "type": "plan_created",
            "task": task,
            "plan": plan,
            "from": "planner"
        })
        
        return {"plan": plan}


@agent("reviewer", responds_to=["plan_created"])
def quality_reviewer(spore):
    """
    I specialize in reviewing and improving the quality of
    plans, solutions, and recommendations.
    """
    task = spore.knowledge.get("task")
    plan = spore.knowledge.get("plan")
    
    # Review with fallback
    try:
        from praval import chat
        review = chat(f"""
        Review this plan for the task "{task}":
        
        {plan}
        
        As a quality specialist, provide:
        - What's working well in this plan
        - Potential improvements or gaps
        - Suggestions for making it more effective
        - Overall assessment
        """)
    except Exception:
        # Fallback review
        review = f"""Quality Review for "{task}":
        
        Strengths: The plan provides a clear phased approach with defined objectives and success criteria. It follows established project management principles.
        
        Potential improvements: Consider adding more specific timelines, risk mitigation strategies, and stakeholder communication plans.
        
        Suggestions: Include regular checkpoints for progress assessment, define clear roles and responsibilities, and establish feedback mechanisms.
        
        Overall assessment: This is a solid foundation that addresses the key aspects of the task. With minor enhancements, it should deliver successful outcomes."""
    
    print(f"⭐ Reviewer: {review}")
    
    # Final summary for the coordinator
    broadcast({
        "type": "quality_review_complete",
        "task": task,
        "review": review,
        "from": "reviewer"
    })
    
    return {"review": review}


@agent("summarizer", responds_to=["quality_review_complete"])
def final_summarizer(spore):
    """
    I specialize in synthesizing contributions from multiple
    agents into coherent final deliverables.
    """
    task = spore.knowledge.get("task")
    review = spore.knowledge.get("review")
    
    # Summary with fallback
    try:
        from praval import chat
        summary = chat(f"""
        Create a final summary for the task: "{task}"
        
        Based on the collaborative effort and quality review: {review}
        
        Provide:
        - What was accomplished through agent collaboration
        - Key insights from the registry-based discovery process
        - How different specialists contributed their expertise
        - The value of dynamic agent coordination
        """)
    except Exception:
        # Fallback summary
        summary = f"""Collaborative Summary for "{task}":
        
        Accomplishments: Through registry-based discovery, multiple specialist agents collaborated to create a comprehensive approach to the task. Each agent contributed their unique expertise when needed.
        
        Discovery insights: The registry system enabled dynamic coordination where agents self-selected based on task requirements, demonstrating loose coupling and adaptive collaboration.
        
        Specialist contributions: The coordinator orchestrated the process, researchers provided context, planners created structure, and reviewers ensured quality - each adding value at the right moment.
        
        Value of coordination: This approach shows how complex tasks can be handled through emergent collaboration rather than rigid orchestration, creating more robust and adaptable solutions."""
    
    print(f"🎯 Summarizer: {summary}")
    
    return {"summary": summary}


def main():
    """Demonstrate registry-based agent discovery and coordination."""
    print("=" * 60)
    print("Example 004: Registry-Based Discovery")
    print("=" * 60)
    
    print("Agents will discover each other through the registry")
    print("and coordinate dynamically based on task needs.")
    print()
    
    # Test with different types of tasks
    tasks = [
        "Design a personal fitness program",
        "Plan a community garden project",
        "Create a reading curriculum for children"
    ]
    
    for i, task in enumerate(tasks, 1):
        print(f"=== Task {i}: {task} ===")
        print()

        # Start all agents - they'll discover and coordinate as needed
        try:
            start_agents(
                task_coordinator,
                research_specialist,
                planning_specialist,
                quality_reviewer,
                final_summarizer,
                initial_data={"task": task}
            )

            # Wait for agents to complete
            get_reef().wait_for_completion()
        except Exception as e:
            print(f"⚠️  Agent coordination completed with some background processing issues (expected without full LLM setup): {e}")

        print("\n" + "─" * 60 + "\n")

    # Shutdown reef after all iterations
    get_reef().shutdown()

    print("Key Insights:")
    print("- Agents discover each other through the registry")
    print("- Coordination happens dynamically based on task needs")
    print("- Specialists self-select when their skills are relevant")
    print("- Loose coupling enables flexible, adaptive collaboration")
    print("- Complex tasks get handled without central orchestration")


if __name__ == "__main__":
    main()