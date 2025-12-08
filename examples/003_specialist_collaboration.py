#!/usr/bin/env python3
"""
Example 003: Specialist Collaboration
=====================================

This example demonstrates how specialized agents collaborate to solve
problems that no single agent could handle alone. Each agent has a
specific expertise, and intelligence emerges from their interaction.

Key Concepts:
- Agent specialization (single responsibility)
- Collaborative problem-solving
- Emergent intelligence from simple interactions
- Sequential and parallel collaboration patterns

Run: python examples/003_specialist_collaboration.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from praval import agent, broadcast, start_agents, get_reef


@agent("analyzer", responds_to=["analyze_problem"])
def problem_analyzer(spore):
    """
    I specialize in breaking down complex problems into their
    constituent parts and identifying key challenges.
    """
    problem = spore.knowledge.get("problem")
    
    # Analysis with fallback
    try:
        from praval import chat
        analysis = chat(f"""
        As an analytical specialist, break down this problem: "{problem}"
        
        Identify:
        - The core challenge
        - 3-4 key aspects that need to be addressed
        - Any constraints or limitations
        
        Be systematic and thorough in your analysis.
        """)
    except Exception:
        # Fallback analysis
        analysis = f"""Problem Analysis: "{problem}"
        
        Core Challenge: This problem requires understanding multiple interconnected factors and stakeholder needs.
        
        Key Aspects:
        1. Stakeholder identification and needs assessment
        2. Resource constraints and availability
        3. Implementation feasibility and timeline
        4. Measurement and evaluation criteria
        
        Constraints: Budget limitations, regulatory requirements, cultural factors, and technological readiness."""
    
    print(f"🔍 Analyzer: {analysis}")
    
    # Send analysis to creative specialists
    broadcast({
        "type": "analysis_complete",
        "problem": problem,
        "analysis": analysis
    })
    
    return {"analysis": analysis}


@agent("creator", responds_to=["analysis_complete"])
def creative_generator(spore):
    """
    I specialize in generating creative, innovative solutions
    based on analytical insights.
    """
    problem = spore.knowledge.get("problem")
    analysis = spore.knowledge.get("analysis")
    
    # Solutions with fallback
    try:
        from praval import chat
        solutions = chat(f"""
        Based on this analysis of the problem "{problem}":
        
        {analysis}
        
        As a creative specialist, generate 3-4 innovative solution approaches.
        Think outside the box while being practical. Focus on creative ideas
        that address the core challenges identified.
        """)
    except Exception:
        # Fallback solutions
        solutions = f"""Creative Solutions for "{problem}":
        
        1. Technology-Enabled Approach: Leverage digital platforms and mobile apps to connect stakeholders and streamline processes.
        
        2. Community-Based Initiative: Build grassroots networks that harness local knowledge and resources for sustainable impact.
        
        3. Partnership Model: Create strategic alliances between public, private, and non-profit sectors to pool resources and expertise.
        
        4. Behavioral Design Solution: Use behavioral economics principles to nudge positive changes through smart defaults and incentives."""
    
    print(f"💡 Creator: {solutions}")
    
    # Send solutions to the evaluator
    broadcast({
        "type": "solutions_generated",
        "problem": problem,
        "analysis": analysis,
        "solutions": solutions
    })
    
    return {"solutions": solutions}


@agent("evaluator", responds_to=["solutions_generated"])
def solution_evaluator(spore):
    """
    I specialize in evaluating solutions for feasibility,
    effectiveness, and potential risks or benefits.
    """
    problem = spore.knowledge.get("problem")
    solutions = spore.knowledge.get("solutions")
    
    # Evaluation with fallback
    try:
        from praval import chat
        evaluation = chat(f"""
        Evaluate these solutions for the problem "{problem}":
        
        {solutions}
        
        As an evaluation specialist, assess each solution for:
        - Feasibility (how realistic is implementation?)
        - Effectiveness (how well does it solve the problem?)
        - Trade-offs (what are the pros and cons?)
        
        Recommend the best approach and explain why.
        """)
    except Exception:
        # Fallback evaluation
        evaluation = f"""Solution Evaluation for "{problem}":
        
        Recommended Approach: Hybrid strategy combining technology and community engagement.
        
        Feasibility: High - leverages existing infrastructure while building new capabilities incrementally.
        
        Effectiveness: Strong potential for impact through multi-stakeholder coordination and scalable implementation.
        
        Trade-offs: 
        - Pro: Sustainable long-term impact, cost-effective resource utilization
        - Con: Requires initial investment in relationship building and technology development
        
        This balanced approach addresses both immediate needs and long-term sustainability."""
    
    print(f"⚖️ Evaluator: {evaluation}")
    
    # Send final evaluation to synthesizer
    broadcast({
        "type": "evaluation_complete",
        "problem": problem,
        "evaluation": evaluation,
        "final_stage": True
    })
    
    return {"evaluation": evaluation}


@agent("synthesizer", responds_to=["evaluation_complete"])
def final_synthesizer(spore):
    """
    I specialize in synthesizing insights from multiple specialists
    into coherent, actionable conclusions.
    """
    if not spore.knowledge.get("final_stage"):
        return  # Only act on final evaluation
    
    problem = spore.knowledge.get("problem")
    evaluation = spore.knowledge.get("evaluation")
    
    # Synthesis with fallback
    try:
        from praval import chat
        synthesis = chat(f"""
        Based on the collaborative analysis for: "{problem}"
        
        Final evaluation: {evaluation}
        
        As a synthesis specialist, create a final summary that:
        - Captures the key insights from all specialists
        - Provides a clear recommended approach
        - Highlights what made this collaborative process effective
        - Shows how the whole became greater than the sum of parts
        """)
    except Exception:
        # Fallback synthesis
        synthesis = f"""Collaborative Analysis Summary: "{problem}"
        
        Key Insights: Through specialist collaboration, we've identified that complex problems require multi-faceted approaches combining analytical rigor, creative thinking, practical evaluation, and strategic synthesis.
        
        Recommended Approach: Implement a phased strategy that starts with stakeholder engagement, builds on proven technologies, and scales through community partnerships.
        
        Collaborative Effectiveness: Each specialist contributed unique perspectives - analytical depth, creative alternatives, practical assessment, and strategic integration. The combination produced richer insights than any single viewpoint.
        
        Emergent Intelligence: The whole became greater than the sum of parts through iterative refinement, where each specialist built upon others' contributions, creating comprehensive solutions that address multiple dimensions of the problem."""
    
    print(f"🎯 Synthesizer: {synthesis}")
    
    return {"synthesis": synthesis}


def main():
    """Demonstrate specialist collaboration."""
    print("=" * 60)
    print("Example 003: Specialist Collaboration")
    print("=" * 60)
    
    print("Four specialists will collaborate to solve complex problems:")
    print("- Analyzer: Breaks down the problem")
    print("- Creator: Generates innovative solutions")
    print("- Evaluator: Assesses feasibility and effectiveness")
    print("- Synthesizer: Creates final actionable insights")
    print()
    
    # Test problems that benefit from multiple perspectives
    problems = [
        "How can we reduce food waste in urban areas?",
        "What's the best way to help people form better habits?",
        "How might we make learning more engaging and effective?"
    ]
    
    for i, problem in enumerate(problems, 1):
        print(f"=== Problem {i}: {problem} ===")
        print()

        # Start all specialists - they'll collaborate through messages
        try:
            start_agents(
                problem_analyzer,
                creative_generator,
                solution_evaluator,
                final_synthesizer,
                initial_data={"type": "analyze_problem", "problem": problem}
            )

            # Wait for agents to complete
            get_reef().wait_for_completion()
        except Exception as e:
            print(f"⚠️  Agent coordination completed with some background processing issues (this is expected without full LLM setup): {e}")

        print("\n" + "─" * 60 + "\n")

    # Shutdown after all iterations
    get_reef().shutdown()

    print("Key Insights:")
    print("- Each agent has a single, clear specialty")
    print("- No central coordinator - agents collaborate naturally")
    print("- Intelligence emerges from the interaction of specialists")
    print("- Complex problems get better solutions through collaboration")
    print("- The whole (collaborative solution) > sum of parts (individual agents)")


if __name__ == "__main__":
    main()