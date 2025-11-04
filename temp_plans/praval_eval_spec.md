# Praval Evaluation Framework
## Technical Specification v1.0

**Status**: Draft  
**Author**: Praval Core Team  
**Date**: November 2024  
**Target Release**: v0.8.0

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Philosophy](#design-philosophy)
3. [Architecture Overview](#architecture-overview)
4. [Core Components](#core-components)
5. [API Specification](#api-specification)
6. [Metrics Framework](#metrics-framework)
7. [Benchmark Suites](#benchmark-suites)
8. [Integration & Tooling](#integration--tooling)
9. [Community Features](#community-features)
10. [Implementation Roadmap](#implementation-roadmap)
11. [Success Metrics](#success-metrics)
12. [Appendices](#appendices)

---

## Executive Summary

### Problem Statement

As Praval grows its ecosystem, developers need:
- **Objective measurement** of agent quality and performance
- **Confidence** in agent behavior before production deployment
- **Benchmarking** capabilities to compare agents and track improvements
- **Standards** for what constitutes a "good" Praval agent

### Solution Overview

A comprehensive evaluation framework that:
- Integrates seamlessly with Praval's decorator-based API
- Provides multi-level evaluation (agent, workflow, system)
- Enables automated testing and continuous evaluation
- Supports community benchmarking and knowledge sharing
- Maintains Praval's philosophy of simplicity and elegance

### Key Value Propositions

**For Developers:**
- ✅ Confidence in agent quality before deployment
- ✅ Quick identification of regressions
- ✅ Clear guidance on improvement areas
- ✅ Comparison against community baselines

**For the Ecosystem:**
- ✅ Standardized evaluation practices
- ✅ Shared benchmark suites
- ✅ Quality signal for agent discovery
- ✅ Research reproducibility

---

## Design Philosophy

### Core Principles

#### 1. **Pythonic & Declarative**
```python
# Evaluation should be as simple as the framework itself
@agent("researcher", responds_to=["research_query"])
@evaluate(metrics=["accuracy", "latency"], benchmark="standard")
def research_agent(spore):
    """I find and analyze information."""
    return result
```

#### 2. **Multi-Level Evaluation**
```
System Level     → Overall reliability, scalability, cost
    ↓
Workflow Level   → Multi-agent coordination, emergent behavior
    ↓
Agent Level      → Individual response quality, performance
```

#### 3. **Developer-Friendly Defaults**
- Zero-config evaluation for basic metrics
- Sensible defaults that work out-of-box
- Progressive disclosure of advanced features
- Clear, actionable feedback

#### 4. **Ecosystem-First**
- Shareable evaluation results
- Community-contributed benchmarks
- Public leaderboards (opt-in)
- Open standards for interoperability

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Decorator-based API** | Matches Praval's existing pattern, minimal code changes |
| **LLM-as-Judge** | Enables semantic evaluation at scale, flexible criteria |
| **JSON Test Scenarios** | Human-readable, version-controllable, tool-friendly |
| **Plugin Architecture** | Community can extend with domain-specific metrics |
| **Async-First** | Efficient evaluation of concurrent agent systems |

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Praval Application                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  @agent("name")                                       │  │
│  │  @evaluate_agent(metrics=["accuracy", "latency"])    │  │
│  │  def my_agent(spore):                                │  │
│  │      return result                                    │  │
│  └────────────────────┬─────────────────────────────────┘  │
└────────────────────────┼────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Evaluation Framework Core                       │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  Decorators  │  │  Collectors  │  │  Metric Engine  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘  │
│         │                  │                    │            │
│         └──────────────────┴────────────────────┘            │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │    Judges    │  │  Benchmarks  │  │    Reporters    │  │
│  │ (LLM/Rule)   │  │   (Suites)   │  │  (HTML/JSON)    │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Storage & Community                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │    Local     │  │  Leaderboard │  │     Plugin      │  │
│  │   Storage    │  │   Backend    │  │    Registry     │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Component Relationships

```mermaid
graph TD
    A[Agent Code] -->|decorated by| B[@evaluate_agent]
    B -->|instruments| C[Metric Collectors]
    C -->|collects| D[Raw Metrics]
    D -->|analyzed by| E[Judges & Scorers]
    E -->|produces| F[Evaluation Results]
    F -->|formatted by| G[Reporters]
    G -->|outputs| H[Reports & Dashboards]
    F -->|compared with| I[Benchmark Suites]
    F -->|stored in| J[Results Database]
    J -->|feeds| K[Leaderboards]
```

### Project Structure

```
praval/
├── src/praval/
│   └── evaluation/
│       ├── __init__.py              # Public API exports
│       ├── decorators.py            # @evaluate_agent, @evaluate_workflow
│       ├── collectors/
│       │   ├── __init__.py
│       │   ├── base.py              # Base collector interface
│       │   ├── performance.py       # Latency, tokens, cost
│       │   ├── quality.py           # Accuracy, relevance
│       │   └── behavior.py          # Memory usage, message patterns
│       ├── judges/
│       │   ├── __init__.py
│       │   ├── base.py              # Judge interface
│       │   ├── llm_judge.py         # LLM-as-judge implementation
│       │   ├── rule_judge.py        # Rule-based evaluation
│       │   └── hybrid_judge.py      # Combined approach
│       ├── metrics/
│       │   ├── __init__.py
│       │   ├── base.py              # Metric definitions
│       │   ├── standard.py          # Built-in metrics
│       │   ├── aggregators.py       # Statistical aggregation
│       │   └── registry.py          # Plugin system for custom metrics
│       ├── benchmarks/
│       │   ├── __init__.py
│       │   ├── loader.py            # Load benchmark suites
│       │   ├── runner.py            # Execute benchmarks
│       │   └── validator.py         # Validate benchmark format
│       ├── reporters/
│       │   ├── __init__.py
│       │   ├── console.py           # Terminal output
│       │   ├── json_reporter.py     # Machine-readable format
│       │   ├── html_reporter.py     # Interactive HTML reports
│       │   └── visualization.py     # Charts and graphs
│       ├── tracing/
│       │   ├── __init__.py
│       │   ├── tracer.py            # Workflow execution tracing
│       │   ├── analyzer.py          # Trace analysis
│       │   └── visualizer.py        # Trace visualization
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── local.py             # Local file storage
│       │   ├── database.py          # Database backend
│       │   └── cloud.py             # Cloud storage (S3, etc.)
│       └── utils/
│           ├── __init__.py
│           ├── stats.py             # Statistical utilities
│           ├── serialization.py     # Data serialization
│           └── comparison.py        # Result comparison
│
├── evaluation/                      # Evaluation assets
│   ├── scenarios/                   # Test scenario library
│   │   ├── single_agent/
│   │   │   ├── reasoning/
│   │   │   │   ├── logical_reasoning.json
│   │   │   │   ├── mathematical_reasoning.json
│   │   │   │   └── causal_reasoning.json
│   │   │   ├── knowledge/
│   │   │   │   ├── factual_qa.json
│   │   │   │   ├── domain_expertise.json
│   │   │   │   └── hallucination_detection.json
│   │   │   ├── generation/
│   │   │   │   ├── creative_writing.json
│   │   │   │   ├── summarization.json
│   │   │   │   └── code_generation.json
│   │   │   └── robustness/
│   │   │       ├── edge_cases.json
│   │   │       ├── adversarial_inputs.json
│   │   │       └── error_handling.json
│   │   ├── multi_agent/
│   │   │   ├── collaboration/
│   │   │   │   ├── task_coordination.json
│   │   │   │   ├── knowledge_sharing.json
│   │   │   │   └── emergent_behavior.json
│   │   │   ├── communication/
│   │   │   │   ├── message_efficiency.json
│   │   │   │   ├── channel_management.json
│   │   │   │   └── broadcast_patterns.json
│   │   │   └── workflows/
│   │   │       ├── sequential_pipeline.json
│   │   │       ├── parallel_processing.json
│   │   │       └── hierarchical_delegation.json
│   │   └── domain_specific/
│   │       ├── research_analysis.json
│   │       ├── content_generation.json
│   │       ├── data_processing.json
│   │       └── customer_support.json
│   ├── benchmarks/                  # Standard benchmark suites
│   │   ├── praval_standard_v1.json  # Core benchmark suite
│   │   ├── hallucination_suite.json # Accuracy benchmarks
│   │   ├── collaboration_suite.json # Multi-agent benchmarks
│   │   └── performance_suite.json   # Speed & efficiency
│   ├── judges/                      # Judge configurations
│   │   ├── accuracy_judge.yaml
│   │   ├── relevance_judge.yaml
│   │   ├── creativity_judge.yaml
│   │   └── safety_judge.yaml
│   └── reports/                     # Generated reports (gitignored)
│       └── .gitkeep
│
├── examples/
│   └── evaluation_examples/
│       ├── 001_basic_agent_eval.py
│       ├── 002_custom_metrics.py
│       ├── 003_workflow_evaluation.py
│       ├── 004_benchmark_comparison.py
│       └── 005_llm_judge_usage.py
│
└── tests/
    └── evaluation/
        ├── test_decorators.py
        ├── test_collectors.py
        ├── test_judges.py
        ├── test_benchmarks.py
        └── test_reporters.py
```

---

## Core Components

### 1. Evaluation Decorators

#### `@evaluate_agent`

**Purpose**: Instrument individual agents for evaluation.

**Signature**:
```python
def evaluate_agent(
    metrics: Optional[List[str]] = None,
    test_cases: Optional[Union[str, List[Dict]]] = None,
    benchmark: Optional[str] = None,
    judges: Optional[Dict[str, Judge]] = None,
    auto_instrument: bool = True,
    store_results: bool = True,
    report_format: str = "console"
) -> Callable
```

**Parameters**:
- `metrics`: List of metric names to collect (e.g., `["accuracy", "latency", "cost"]`)
- `test_cases`: Path to JSON file or list of test scenarios
- `benchmark`: Name of standard benchmark suite to run
- `judges`: Custom judge instances for specific criteria
- `auto_instrument`: Automatically collect basic metrics
- `store_results`: Save results to disk
- `report_format`: Output format (`"console"`, `"json"`, `"html"`, `"all"`)

**Usage**:
```python
from praval import agent
from praval.evaluation import evaluate_agent

@agent("researcher", responds_to=["research_query"])
@evaluate_agent(
    metrics=["accuracy", "relevance", "latency"],
    test_cases="evaluation/scenarios/single_agent/knowledge/factual_qa.json",
    report_format="html"
)
def research_agent(spore):
    """I find and analyze information."""
    query = spore.knowledge.get("query")
    result = deep_research(query)
    return {"findings": result}
```

#### `@evaluate_workflow`

**Purpose**: Evaluate multi-agent workflows and coordination.

**Signature**:
```python
def evaluate_workflow(
    agents: List[Callable],
    scenarios: Union[str, List[Dict]],
    success_criteria: Optional[Dict[str, float]] = None,
    trace: bool = True,
    visualize: bool = False,
    compare_to: Optional[str] = None
) -> Callable
```

**Parameters**:
- `agents`: List of agent functions in the workflow
- `scenarios`: Multi-agent test scenarios
- `success_criteria`: Required thresholds (e.g., `{"completion_rate": 0.95}`)
- `trace`: Enable execution tracing
- `visualize`: Generate workflow visualization
- `compare_to`: Path to baseline results for comparison

**Usage**:
```python
from praval.evaluation import evaluate_workflow

@evaluate_workflow(
    agents=[researcher, analyzer, writer],
    scenarios="evaluation/scenarios/multi_agent/workflows/sequential_pipeline.json",
    success_criteria={
        "completion_rate": 0.95,
        "avg_latency": 10.0,
        "collaboration_score": 0.8
    },
    trace=True,
    visualize=True
)
def research_pipeline():
    """Complete research and analysis workflow."""
    start_agents(
        researcher,
        analyzer,
        writer,
        initial_data={"type": "research_query", "topic": "quantum computing"}
    )
```

### 2. Metric Collectors

#### Base Collector Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class MetricCollector(ABC):
    """Base class for metric collectors."""
    
    @abstractmethod
    def start_collection(self, context: Dict[str, Any]) -> None:
        """Initialize collection for an agent execution."""
        pass
    
    @abstractmethod
    def collect(self, event: Dict[str, Any]) -> None:
        """Collect a single measurement."""
        pass
    
    @abstractmethod
    def finalize(self) -> Dict[str, Any]:
        """Compute final metrics."""
        pass
    
    @property
    @abstractmethod
    def metric_names(self) -> List[str]:
        """Names of metrics this collector provides."""
        pass
```

#### Built-in Collectors

**PerformanceCollector**:
```python
class PerformanceCollector(MetricCollector):
    """Collects performance metrics."""
    
    metric_names = ["latency", "tokens_used", "cost"]
    
    def collect(self, event: Dict[str, Any]) -> None:
        if event["type"] == "llm_request":
            self.token_count += event["tokens"]
            self.cost += calculate_cost(event["model"], event["tokens"])
```

**QualityCollector**:
```python
class QualityCollector(MetricCollector):
    """Collects quality metrics using judges."""
    
    metric_names = ["accuracy", "relevance", "coherence"]
    
    def finalize(self) -> Dict[str, Any]:
        return {
            "accuracy": self.judge.evaluate(self.responses, self.references),
            "relevance": self.relevance_score(),
            "coherence": self.coherence_score()
        }
```

**BehaviorCollector**:
```python
class BehaviorCollector(MetricCollector):
    """Collects behavioral metrics."""
    
    metric_names = ["message_count", "memory_usage", "error_rate"]
    
    def collect(self, event: Dict[str, Any]) -> None:
        if event["type"] == "reef_message":
            self.messages_sent += 1
        elif event["type"] == "error":
            self.errors += 1
```

### 3. Judges

#### LLM Judge

```python
from praval.evaluation import LLMJudge

judge = LLMJudge(
    criteria={
        "accuracy": {
            "description": "Is the information factually correct?",
            "scale": "1-10",
            "examples": [
                {"score": 10, "reason": "All facts verified and precise"},
                {"score": 5, "reason": "Some inaccuracies present"},
                {"score": 1, "reason": "Mostly incorrect information"}
            ]
        },
        "relevance": {
            "description": "Does the response address the query directly?",
            "scale": "1-10",
            "rubric": """
            10: Perfectly addresses all aspects
            7-9: Addresses most aspects with minor gaps
            4-6: Partially relevant with significant gaps
            1-3: Largely irrelevant or off-topic
            """
        }
    },
    model="gpt-4o",  # Judge model
    temperature=0.0,  # Deterministic scoring
    use_chain_of_thought=True  # Explain reasoning
)

# Evaluate a response
result = judge.evaluate(
    input={"query": "What is quantum entanglement?"},
    output={"answer": "Quantum entanglement is..."},
    reference={"ground_truth": "Quantum entanglement..."}  # Optional
)

# Result structure:
# {
#     "accuracy": {"score": 9, "reasoning": "..."},
#     "relevance": {"score": 10, "reasoning": "..."},
#     "overall_score": 9.5
# }
```

#### Rule-Based Judge

```python
from praval.evaluation import RuleJudge

judge = RuleJudge(rules={
    "length_check": lambda text: 100 <= len(text) <= 500,
    "no_profanity": lambda text: not contains_profanity(text),
    "contains_citations": lambda text: has_citations(text),
    "proper_format": lambda text: is_valid_json(text)
})

result = judge.evaluate(output=response)
# Returns pass/fail for each rule
```

#### Hybrid Judge

```python
from praval.evaluation import HybridJudge

judge = HybridJudge(
    rules={
        "format_valid": lambda x: validate_format(x),
        "length_appropriate": lambda x: 50 <= len(x) <= 1000
    },
    llm_criteria={
        "quality": "Rate the quality of reasoning (1-10)",
        "creativity": "Rate the creativity of the solution (1-10)"
    },
    weights={"rules": 0.3, "llm": 0.7}  # Weighted combination
)
```

### 4. Benchmark Suites

#### Standard Benchmark Format

```json
{
  "name": "praval_standard_v1",
  "version": "1.0.0",
  "description": "Standard benchmark for Praval agents",
  "categories": {
    "reasoning": {
      "description": "Logical reasoning and problem-solving",
      "test_cases": [
        {
          "id": "reasoning_001",
          "input": {
            "type": "research_query",
            "query": "If all roses are flowers and some flowers fade quickly, can we conclude that some roses fade quickly?"
          },
          "expected_output": {
            "answer": "No, this conclusion cannot be drawn from the given premises.",
            "reasoning": "The syllogism commits the fallacy of the undistributed middle..."
          },
          "criteria": {
            "accuracy": {"weight": 0.6, "threshold": 0.8},
            "reasoning_quality": {"weight": 0.4, "threshold": 0.7}
          },
          "tags": ["logic", "syllogism", "formal_reasoning"]
        }
      ],
      "success_threshold": 0.80
    },
    "collaboration": {
      "description": "Multi-agent coordination",
      "test_cases": [...],
      "success_threshold": 0.85
    }
  },
  "overall_passing_score": 0.75
}
```

#### Benchmark Runner

```python
from praval.evaluation import run_benchmark

results = run_benchmark(
    agent=research_agent,
    benchmark="praval_standard_v1",
    categories=["reasoning", "knowledge"],  # Optional: run specific categories
    verbose=True,
    save_results=True
)

# Results structure:
# {
#     "benchmark": "praval_standard_v1",
#     "agent": "research_agent",
#     "timestamp": "2024-11-03T10:30:00Z",
#     "overall_score": 0.87,
#     "passed": True,
#     "categories": {
#         "reasoning": {
#             "score": 0.85,
#             "test_cases_passed": 17,
#             "test_cases_total": 20,
#             "details": [...]
#         }
#     }
# }
```

### 5. Reporters

#### Console Reporter

```python
from praval.evaluation import ConsoleReporter

reporter = ConsoleReporter(
    color=True,
    show_details=True,
    show_suggestions=True
)

reporter.generate(results)
# Output:
# ╭─────────────────────────────────────────╮
# │   Evaluation Results: research_agent    │
# ╰─────────────────────────────────────────╯
#
# Overall Score: 87% ✅
#
# ┌─────────────────────┬────────┬──────────┐
# │ Metric              │ Score  │ Status   │
# ├─────────────────────┼────────┼──────────┤
# │ Accuracy            │  90%   │    ✅    │
# │ Relevance           │  88%   │    ✅    │
# │ Latency (avg)       │ 1.2s   │    ✅    │
# │ Cost per 1k reqs    │ $0.05  │    ✅    │
# └─────────────────────┴────────┴──────────┘
#
# 💡 Suggestions:
#   • Consider caching for repeated queries
#   • Latency could be improved with streaming
```

#### HTML Reporter

```python
from praval.evaluation import HTMLReporter

reporter = HTMLReporter(
    template="default",
    include_charts=True,
    include_traces=True,
    interactive=True
)

reporter.generate(results, output="evaluation_report.html")
```

**HTML Report Features**:
- Interactive charts (latency distribution, accuracy over time)
- Collapsible test case details
- Workflow trace visualization
- Comparison with previous runs
- Exportable to PDF

#### JSON Reporter

```python
from praval.evaluation import JSONReporter

reporter = JSONReporter(
    pretty_print=True,
    include_metadata=True
)

reporter.generate(results, output="evaluation_results.json")
```

---

## API Specification

### Quick Start API

#### Simplest Usage (Zero Configuration)

```python
from praval import agent
from praval.evaluation import evaluate_agent

@agent("simple", responds_to=["query"])
@evaluate_agent()  # Uses all defaults
def simple_agent(spore):
    return {"answer": "result"}

# Automatic evaluation on every call
# Metrics: latency, tokens, cost (basic performance)
# Report: Console output
```

#### Basic Custom Configuration

```python
@agent("researcher", responds_to=["research_query"])
@evaluate_agent(
    metrics=["accuracy", "relevance", "latency"],
    report_format="html"
)
def research_agent(spore):
    return result
```

#### Advanced Configuration

```python
from praval.evaluation import LLMJudge, evaluate_agent

custom_judge = LLMJudge(
    criteria={
        "domain_expertise": "Does the response demonstrate deep domain knowledge?",
        "citation_quality": "Are sources properly cited and credible?"
    }
)

@agent("domain_expert", responds_to=["expert_query"])
@evaluate_agent(
    metrics=["accuracy", "domain_expertise", "citation_quality"],
    test_cases="evaluation/scenarios/domain_specific/medical_qa.json",
    judges={"domain_expertise": custom_judge, "citation_quality": custom_judge},
    benchmark="medical_expert_v1",
    success_criteria={"accuracy": 0.95, "domain_expertise": 0.90},
    store_results=True,
    report_format="all"  # console + html + json
)
def medical_expert_agent(spore):
    return expert_analysis(spore.knowledge["query"])
```

### Programmatic Evaluation API

#### Evaluate Without Decorator

```python
from praval.evaluation import AgentEvaluator

# Create evaluator
evaluator = AgentEvaluator(
    agent=research_agent,
    metrics=["accuracy", "latency", "cost"],
    test_cases="test_scenarios.json"
)

# Run evaluation
results = evaluator.run()

# Access results
print(f"Overall Score: {results.overall_score}")
print(f"Accuracy: {results.metrics['accuracy']}")
print(f"Average Latency: {results.metrics['latency']['mean']}s")

# Compare with baseline
comparison = evaluator.compare_to("baseline_results.json")
if comparison.regression_detected:
    print(f"⚠️  Regression in: {comparison.regressed_metrics}")
```

#### Batch Evaluation

```python
from praval.evaluation import evaluate_multiple_agents

results = evaluate_multiple_agents(
    agents=[agent1, agent2, agent3],
    benchmark="praval_standard_v1",
    comparison_mode=True  # Generate comparison report
)

# Get rankings
rankings = results.rank_by("overall_score")
for rank, (agent_name, score) in enumerate(rankings, 1):
    print(f"{rank}. {agent_name}: {score}")
```

#### Workflow Evaluation API

```python
from praval.evaluation import WorkflowEvaluator

evaluator = WorkflowEvaluator(
    agents=[researcher, analyzer, writer],
    scenarios="multi_agent_scenarios.json",
    trace=True
)

# Run evaluation
results = evaluator.run()

# Access workflow-specific metrics
print(f"Completion Rate: {results.completion_rate}")
print(f"Average End-to-End Latency: {results.total_latency_mean}s")
print(f"Message Passing Efficiency: {results.message_efficiency}")
print(f"Collaboration Score: {results.collaboration_score}")

# Visualize workflow
trace_viz = evaluator.visualize_trace()
trace_viz.save("workflow_trace.html")
```

### Custom Metrics API

#### Creating Custom Metrics

```python
from praval.evaluation import register_metric, MetricCollector

@register_metric("domain_relevance")
class DomainRelevanceCollector(MetricCollector):
    """Custom metric for domain-specific relevance."""
    
    def __init__(self, domain_keywords: List[str]):
        self.domain_keywords = domain_keywords
        self.scores = []
    
    def collect(self, event: Dict[str, Any]) -> None:
        if event["type"] == "agent_response":
            score = self._calculate_relevance(
                event["response"],
                self.domain_keywords
            )
            self.scores.append(score)
    
    def finalize(self) -> Dict[str, Any]:
        return {
            "domain_relevance": {
                "mean": np.mean(self.scores),
                "std": np.std(self.scores),
                "min": min(self.scores),
                "max": max(self.scores)
            }
        }
    
    def _calculate_relevance(self, text: str, keywords: List[str]) -> float:
        # Custom scoring logic
        matches = sum(1 for kw in keywords if kw.lower() in text.lower())
        return matches / len(keywords)

# Use custom metric
@evaluate_agent(metrics=["accuracy", "domain_relevance"])
def specialized_agent(spore):
    return result
```

#### Custom Judge

```python
from praval.evaluation import register_judge, Judge

@register_judge("code_quality")
class CodeQualityJudge(Judge):
    """Judge for code generation quality."""
    
    def evaluate(self, input: Dict, output: Dict, reference: Dict = None) -> Dict:
        code = output.get("code", "")
        
        scores = {
            "syntax_valid": self._check_syntax(code),
            "follows_conventions": self._check_conventions(code),
            "has_docstrings": self._check_docs(code),
            "test_coverage": self._check_tests(code, output.get("tests"))
        }
        
        overall = sum(scores.values()) / len(scores)
        
        return {
            "score": overall,
            "details": scores,
            "reasoning": self._generate_feedback(scores)
        }
```

### Testing Integration API

#### pytest Integration

```python
# test_agents.py
import pytest
from praval.evaluation import evaluate_agent_function

def test_research_agent_accuracy():
    """Test research agent meets accuracy threshold."""
    results = evaluate_agent_function(
        agent_func=research_agent,
        test_cases="test_scenarios/research.json",
        metrics=["accuracy"]
    )
    
    assert results.metrics["accuracy"] >= 0.90, \
        f"Accuracy {results.metrics['accuracy']} below threshold"

def test_research_agent_performance():
    """Test research agent performance requirements."""
    results = evaluate_agent_function(
        agent_func=research_agent,
        test_cases="test_scenarios/research.json",
        metrics=["latency", "cost"]
    )
    
    assert results.metrics["latency"]["p95"] < 5.0, \
        f"P95 latency {results.metrics['latency']['p95']}s exceeds 5s"
    
    assert results.metrics["cost"]["per_1k_requests"] < 0.10, \
        f"Cost ${results.metrics['cost']['per_1k_requests']} exceeds $0.10"

@pytest.mark.benchmark
def test_against_standard_benchmark():
    """Test against Praval standard benchmark."""
    results = evaluate_agent_function(
        agent_func=research_agent,
        benchmark="praval_standard_v1",
        categories=["reasoning", "knowledge"]
    )
    
    assert results.overall_score >= 0.75, \
        f"Overall score {results.overall_score} below passing threshold"
```

#### Continuous Evaluation

```python
# evaluation_config.yaml
agents:
  - name: research_agent
    module: agents.research
    metrics: [accuracy, latency, cost]
    benchmark: praval_standard_v1
    thresholds:
      accuracy: 0.90
      latency_p95: 5.0
  
  - name: analysis_agent
    module: agents.analysis
    metrics: [accuracy, coherence, depth]
    test_cases: evaluation/scenarios/analysis_scenarios.json

workflows:
  - name: research_pipeline
    agents: [research_agent, analysis_agent, writer_agent]
    scenarios: evaluation/scenarios/workflows/research_workflow.json
    success_criteria:
      completion_rate: 0.95
      avg_latency: 15.0

reporting:
  formats: [console, html, json]
  output_dir: evaluation/reports
  upload_to_leaderboard: false
```

```bash
# Run continuous evaluation
praval evaluate --config evaluation_config.yaml --ci

# Output:
# ✅ research_agent: PASSED (score: 0.92)
# ✅ analysis_agent: PASSED (score: 0.88)
# ⚠️  writer_agent: WARNING (latency p95: 5.2s, threshold: 5.0s)
# ✅ research_pipeline: PASSED (completion: 97%)
#
# Overall: 3/3 agents passed, 1 warning
```

---

## Metrics Framework

### Standard Metrics

#### Performance Metrics

| Metric | Description | Unit | Collection Method |
|--------|-------------|------|-------------------|
| `latency` | Response time | seconds | Timestamp diff |
| `tokens_used` | LLM tokens consumed | count | Provider API |
| `cost` | Estimated cost | USD | Token count × pricing |
| `throughput` | Requests per second | req/s | Time window analysis |
| `memory_usage` | RAM consumption | MB | Process monitoring |

**Example Output**:
```json
{
  "latency": {
    "mean": 1.234,
    "median": 1.150,
    "p95": 2.100,
    "p99": 3.450,
    "std": 0.567
  },
  "tokens_used": {
    "total": 12450,
    "input": 8230,
    "output": 4220,
    "mean_per_request": 124.5
  },
  "cost": {
    "total": 0.0623,
    "per_request": 0.000623,
    "per_1k_requests": 0.623
  }
}
```

#### Quality Metrics

| Metric | Description | Scale | Evaluation Method |
|--------|-------------|-------|-------------------|
| `accuracy` | Factual correctness | 0-1 | LLM judge / Reference comparison |
| `relevance` | Query alignment | 0-1 | LLM judge / Semantic similarity |
| `coherence` | Logical consistency | 0-1 | LLM judge / Rule-based |
| `completeness` | Coverage of aspects | 0-1 | Checklist / LLM judge |
| `hallucination_rate` | False information | 0-1 | Fact-checking / LLM judge |

**Example Output**:
```json
{
  "accuracy": {
    "score": 0.92,
    "judgments": {
      "correct": 46,
      "incorrect": 4,
      "total": 50
    },
    "confidence_intervals": {
      "lower": 0.88,
      "upper": 0.95
    }
  },
  "relevance": {
    "score": 0.87,
    "distribution": {
      "highly_relevant": 32,
      "somewhat_relevant": 15,
      "not_relevant": 3
    }
  }
}
```

#### Behavioral Metrics

| Metric | Description | Unit | Collection Method |
|--------|-------------|------|-------------------|
| `message_count` | Reef messages sent | count | Reef instrumentation |
| `memory_retrieval_rate` | Memory queries per response | count | Memory system hooks |
| `tool_usage` | External tool calls | count | Tool registry |
| `error_rate` | Failed requests | percentage | Exception tracking |
| `retry_rate` | Retry attempts | percentage | Retry logic instrumentation |

**Example Output**:
```json
{
  "message_count": {
    "total": 150,
    "broadcast": 45,
    "unicast": 105,
    "mean_per_agent_call": 3.0
  },
  "error_rate": 0.04,
  "retry_rate": 0.12,
  "successful_after_retry": 0.08
}
```

#### Multi-Agent Metrics

| Metric | Description | Scale | Evaluation Method |
|--------|-------------|-------|-------------------|
| `collaboration_score` | Coordination effectiveness | 0-1 | Workflow analysis |
| `message_efficiency` | Communication overhead | 0-1 | Message/task ratio |
| `task_completion_rate` | Successful completions | 0-1 | Success counting |
| `handoff_success_rate` | Clean task transitions | 0-1 | Handoff tracking |
| `emergent_capability` | Collective > individual | 0-1 | Comparative eval |

**Example Output**:
```json
{
  "collaboration_score": 0.85,
  "workflow_analysis": {
    "total_tasks": 50,
    "completed": 47,
    "partial": 2,
    "failed": 1,
    "completion_rate": 0.94
  },
  "message_efficiency": {
    "messages_per_task": 4.2,
    "productive_messages": 0.82,
    "redundant_messages": 0.18
  },
  "emergent_capability": {
    "multi_agent_score": 0.88,
    "best_individual_score": 0.65,
    "improvement": 0.35
  }
}
```

### Metric Aggregation

#### Statistical Aggregation

```python
from praval.evaluation import MetricAggregator

aggregator = MetricAggregator()

# Add individual measurements
for result in test_results:
    aggregator.add_measurement("accuracy", result.accuracy)
    aggregator.add_measurement("latency", result.latency)

# Get aggregated statistics
stats = aggregator.get_statistics()

# Output:
# {
#     "accuracy": {
#         "mean": 0.92,
#         "median": 0.93,
#         "std": 0.05,
#         "min": 0.78,
#         "max": 0.98,
#         "confidence_interval": (0.90, 0.94)
#     },
#     "latency": {...}
# }
```

#### Time-Series Analysis

```python
from praval.evaluation import TimeSeriesAnalyzer

analyzer = TimeSeriesAnalyzer()

# Detect trends
trend = analyzer.detect_trend(
    metric="accuracy",
    values=historical_accuracy,
    timestamps=historical_timestamps
)

if trend.direction == "decreasing" and trend.significance > 0.05:
    print(f"⚠️  Accuracy degrading: {trend.slope:.4f} per day")

# Detect anomalies
anomalies = analyzer.detect_anomalies(
    metric="latency",
    values=latency_measurements
)
```

### Metric Visualization

```python
from praval.evaluation import MetricVisualizer

viz = MetricVisualizer()

# Create comparison chart
viz.compare_metrics(
    agents=["agent_v1", "agent_v2", "agent_v3"],
    metric="accuracy",
    data=comparison_data
).save("accuracy_comparison.png")

# Create time-series plot
viz.plot_timeseries(
    metric="latency",
    data=historical_data,
    annotations=["v1.0 release", "v2.0 release"]
).save("latency_over_time.png")

# Create distribution plot
viz.plot_distribution(
    metric="response_length",
    data=response_lengths
).save("response_length_dist.png")
```

---

## Benchmark Suites

### Praval Standard Benchmark v1

#### Overview

The Praval Standard Benchmark is a comprehensive evaluation suite designed to assess core capabilities of Praval agents across multiple dimensions.

**Coverage Areas**:
- Reasoning & Logic (20 test cases)
- Knowledge & Factuality (25 test cases)
- Creative Generation (15 test cases)
- Robustness & Edge Cases (20 test cases)
- Multi-Agent Collaboration (20 test cases)
- **Total**: 100 test cases

#### Category Details

##### 1. Reasoning & Logic

**Test Types**:
- Logical syllogisms
- Mathematical reasoning
- Causal inference
- Analogical reasoning
- Common sense reasoning

**Example Test Case**:
```json
{
  "id": "reasoning_001",
  "category": "reasoning",
  "subcategory": "logical_syllogism",
  "input": {
    "type": "query",
    "query": "If all roses are flowers and some flowers fade quickly, can we conclude that some roses fade quickly?"
  },
  "expected_output": {
    "answer": "No",
    "reasoning": "The conclusion does not logically follow. The premise states that SOME flowers fade quickly, but does not specify whether roses are among those flowers. This commits the fallacy of the undistributed middle term."
  },
  "evaluation_criteria": {
    "correctness": {
      "weight": 0.6,
      "judge": "rule_based",
      "rule": "answer must be 'No' or equivalent"
    },
    "reasoning_quality": {
      "weight": 0.4,
      "judge": "llm",
      "prompt": "Rate the quality of logical reasoning (0-10)"
    }
  },
  "difficulty": "medium",
  "tags": ["logic", "syllogism", "formal_reasoning"]
}
```

##### 2. Knowledge & Factuality

**Test Types**:
- Factual question answering
- Domain expertise verification
- Hallucination detection
- Source attribution
- Temporal knowledge

**Example Test Case**:
```json
{
  "id": "knowledge_001",
  "category": "knowledge",
  "subcategory": "factual_qa",
  "input": {
    "type": "query",
    "query": "What is the speed of light in a vacuum, and who first measured it accurately?"
  },
  "expected_output": {
    "speed": "299,792,458 meters per second",
    "scientist": "Ole Rømer (1676) provided first evidence; modern accurate measurements by various scientists in 20th century",
    "facts_verified": true
  },
  "evaluation_criteria": {
    "factual_accuracy": {
      "weight": 0.7,
      "judge": "rule_based",
      "verification": "check against known facts"
    },
    "completeness": {
      "weight": 0.3,
      "judge": "llm",
      "prompt": "Does the answer cover all aspects of the question?"
    }
  },
  "difficulty": "easy",
  "tags": ["physics", "history_of_science", "measurement"]
}
```

##### 3. Creative Generation

**Test Types**:
- Story writing
- Poetry generation
- Code synthesis
- Summarization
- Style transfer

**Evaluation**: Primarily LLM-judged for creativity, coherence, style adherence

##### 4. Robustness & Edge Cases

**Test Types**:
- Ambiguous queries
- Adversarial inputs
- Out-of-distribution data
- Malformed requests
- Context length stress tests

**Example Test Case**:
```json
{
  "id": "robustness_001",
  "category": "robustness",
  "subcategory": "ambiguous_query",
  "input": {
    "type": "query",
    "query": "What is the capital of Turkey?"
  },
  "expected_behaviors": [
    "Recognizes ambiguity (country vs. bird)",
    "Asks for clarification OR provides both interpretations",
    "Does not assume one meaning without acknowledgment"
  ],
  "evaluation_criteria": {
    "ambiguity_handling": {
      "weight": 1.0,
      "judge": "llm",
      "prompt": "Does the agent appropriately handle the ambiguity? (0-10)"
    }
  },
  "difficulty": "medium",
  "tags": ["ambiguity", "clarification", "robustness"]
}
```

##### 5. Multi-Agent Collaboration

**Test Types**:
- Task coordination
- Knowledge sharing
- Conflict resolution
- Emergent behavior
- Workflow completion

**Example Test Case**:
```json
{
  "id": "collaboration_001",
  "category": "collaboration",
  "subcategory": "task_coordination",
  "scenario": {
    "description": "Three agents must collaborate to write a research report",
    "agents": ["researcher", "analyst", "writer"],
    "initial_data": {
      "type": "research_request",
      "topic": "renewable energy trends 2024"
    },
    "expected_workflow": [
      "researcher gathers information",
      "analyst processes and analyzes data",
      "writer composes final report"
    ]
  },
  "success_criteria": {
    "workflow_completion": {
      "weight": 0.4,
      "threshold": 1.0,
      "description": "All steps completed successfully"
    },
    "message_efficiency": {
      "weight": 0.2,
      "threshold": 0.7,
      "description": "Low communication overhead"
    },
    "output_quality": {
      "weight": 0.4,
      "threshold": 0.8,
      "judge": "llm",
      "prompt": "Rate the quality of the final report (0-10)"
    }
  },
  "timeout": 60,
  "difficulty": "hard",
  "tags": ["coordination", "workflow", "multi_agent"]
}
```

#### Benchmark Results Format

```json
{
  "benchmark": "praval_standard_v1",
  "version": "1.0.0",
  "agent": {
    "name": "research_agent",
    "version": "2.1.0",
    "description": "Research and analysis specialist"
  },
  "execution": {
    "timestamp": "2024-11-03T10:30:00Z",
    "duration_seconds": 458.23,
    "environment": {
      "praval_version": "0.8.0",
      "python_version": "3.11.5",
      "llm_provider": "openai",
      "llm_model": "gpt-4o"
    }
  },
  "results": {
    "overall_score": 0.87,
    "passed": true,
    "passing_threshold": 0.75,
    "categories": {
      "reasoning": {
        "score": 0.85,
        "test_cases_total": 20,
        "test_cases_passed": 17,
        "test_cases_failed": 3,
        "pass_threshold": 0.80,
        "passed": true
      },
      "knowledge": {
        "score": 0.91,
        "test_cases_total": 25,
        "test_cases_passed": 23,
        "test_cases_failed": 2,
        "pass_threshold": 0.85,
        "passed": true
      },
      "creative": {
        "score": 0.82,
        "test_cases_total": 15,
        "test_cases_passed": 13,
        "test_cases_failed": 2,
        "pass_threshold": 0.75,
        "passed": true
      },
      "robustness": {
        "score": 0.88,
        "test_cases_total": 20,
        "test_cases_passed": 18,
        "test_cases_failed": 2,
        "pass_threshold": 0.80,
        "passed": true
      },
      "collaboration": {
        "score": 0.89,
        "test_cases_total": 20,
        "test_cases_passed": 18,
        "test_cases_failed": 2,
        "pass_threshold": 0.85,
        "passed": true
      }
    },
    "performance": {
      "avg_latency_seconds": 1.85,
      "total_tokens": 125340,
      "total_cost_usd": 0.6267
    }
  }
}
```

### Domain-Specific Benchmarks

#### Medical QA Benchmark
- Focus: Medical knowledge, diagnostic reasoning, safety
- Test cases: 150
- Special requirements: High accuracy threshold (>0.95), harm prevention

#### Code Generation Benchmark
- Focus: Syntax correctness, efficiency, documentation
- Test cases: 100
- Languages: Python, JavaScript, Java, C++
- Evaluation: Automated testing + code quality metrics

#### Customer Support Benchmark
- Focus: Empathy, problem-solving, escalation handling
- Test cases: 80
- Evaluation: Customer satisfaction proxy metrics

### Creating Custom Benchmarks

```python
from praval.evaluation import BenchmarkBuilder

builder = BenchmarkBuilder(
    name="custom_domain_benchmark",
    version="1.0.0",
    description="Benchmark for my specific domain"
)

# Add test category
builder.add_category(
    name="domain_knowledge",
    description="Test domain-specific knowledge",
    pass_threshold=0.85
)

# Add test cases
builder.add_test_case(
    category="domain_knowledge",
    test_id="dk_001",
    input={"query": "..."},
    expected_output={"answer": "..."},
    criteria={
        "accuracy": {"weight": 0.7, "judge": "llm"},
        "depth": {"weight": 0.3, "judge": "custom_depth_judge"}
    }
)

# Save benchmark
builder.save("evaluation/benchmarks/custom_domain_v1.json")

# Validate benchmark structure
builder.validate()
```

---

## Integration & Tooling

### CI/CD Integration

#### GitHub Actions Example

```yaml
# .github/workflows/evaluate_agents.yml
name: Evaluate Agents

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install praval[all]
          pip install -r requirements.txt
      
      - name: Run Agent Evaluation
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          praval evaluate \
            --config evaluation_config.yaml \
            --report-format json \
            --output evaluation_results.json
      
      - name: Check Thresholds
        run: |
          python -c "
          import json
          with open('evaluation_results.json') as f:
              results = json.load(f)
          if results['overall_score'] < 0.75:
              raise Exception(f\"Score {results['overall_score']} below threshold\")
          "
      
      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: evaluation-results
          path: evaluation_results.json
      
      - name: Comment PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const results = require('./evaluation_results.json');
            const comment = `
            ## 🎯 Agent Evaluation Results
            
            Overall Score: **${results.overall_score.toFixed(2)}** ${results.passed ? '✅' : '❌'}
            
            | Category | Score | Status |
            |----------|-------|--------|
            ${Object.entries(results.categories).map(([cat, data]) => 
              `| ${cat} | ${data.score.toFixed(2)} | ${data.passed ? '✅' : '❌'} |`
            ).join('\n')}
            `;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
```

#### Pre-commit Hook

```python
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: evaluate-agents
        name: Evaluate Changed Agents
        entry: python scripts/evaluate_changed_agents.py
        language: python
        pass_filenames: true
        files: 'agents/.*\.py$'
```

```python
# scripts/evaluate_changed_agents.py
import sys
from praval.evaluation import evaluate_agent_file

changed_files = sys.argv[1:]
failed = []

for file in changed_files:
    if 'agents/' in file and file.endswith('.py'):
        results = evaluate_agent_file(
            file,
            quick_mode=True,  # Fast smoke test
            threshold=0.70
        )
        
        if not results.passed:
            failed.append(f"{file}: {results.overall_score:.2f}")

if failed:
    print("❌ Agent evaluation failed:")
    for failure in failed:
        print(f"  - {failure}")
    sys.exit(1)

print("✅ All agents passed evaluation")
```

### IDE Integration

#### VSCode Extension Features

```json
{
  "praval.evaluation": {
    "enableInlineMetrics": true,
    "showQuickEval": true,
    "autoEvaluateOnSave": false,
    "defaultBenchmark": "praval_standard_v1"
  }
}
```

**Features**:
- Inline metric display (CodeLens)
- Quick evaluation command (`Cmd+Shift+E`)
- Benchmark selection from palette
- Live evaluation results panel
- Warning decorations for failing tests

#### JupyterLab Extension

```python
# In Jupyter cell
%praval_eval research_agent --quick

# Output:
# ┌─────────────────────┬────────┐
# │ Metric              │ Score  │
# ├─────────────────────┼────────┤
# │ Accuracy            │  0.92  │
# │ Latency             │  1.2s  │
# │ Cost (per 1k)       │ $0.05  │
# └─────────────────────┴────────┘
```

### CLI Tools

#### Main CLI Commands

```bash
# Run evaluation on specific agent
praval evaluate research_agent \
  --benchmark praval_standard_v1 \
  --report html \
  --output report.html

# Evaluate all agents in directory
praval evaluate agents/ \
  --config evaluation_config.yaml \
  --parallel 4

# Quick smoke test
praval evaluate research_agent --quick

# Compare agents
praval compare agent_v1 agent_v2 agent_v3 \
  --benchmark praval_standard_v1 \
  --output comparison.html

# Run specific benchmark category
praval evaluate research_agent \
  --benchmark praval_standard_v1 \
  --categories reasoning,knowledge

# Validate benchmark file
praval validate-benchmark evaluation/benchmarks/custom.json

# Generate evaluation report from saved results
praval report evaluation_results.json \
  --format html \
  --output report.html
```

#### Advanced CLI Features

```bash
# Continuous evaluation (watch mode)
praval evaluate agents/ --watch --auto-rerun

# Regression testing
praval regression-test \
  --baseline results/baseline_v1.json \
  --current results/current.json \
  --threshold 0.05

# Generate test cases
praval generate-tests \
  --agent research_agent \
  --count 50 \
  --difficulty medium,hard \
  --output test_cases.json

# Upload results to leaderboard
praval upload-results \
  --results evaluation_results.json \
  --leaderboard public \
  --anonymous

# Download benchmark
praval download-benchmark medical_qa_v1 \
  --output evaluation/benchmarks/
```

---

## Community Features

### Public Leaderboard

#### Overview

An opt-in leaderboard system that enables community comparison and fosters healthy competition while protecting privacy.

#### Features

**1. Multiple Leaderboards**:
- Global: All agents across all categories
- Category-Specific: Best in reasoning, knowledge, creativity, etc.
- Domain-Specific: Medical, legal, creative, etc.
- Time-Based: Daily, weekly, monthly, all-time

**2. Privacy Options**:
- Anonymous submission (no identifying information)
- Pseudonymous (chosen display name)
- Attributed (linked to developer/organization)

**3. Verification Levels**:
- 🔵 Unverified: Self-reported results
- 🟢 Automated: Results from official evaluation tool
- 🟡 Reviewed: Manual review by maintainers
- 🔴 Certified: Passed rigorous third-party audit

#### Leaderboard API

```python
from praval.evaluation import upload_to_leaderboard

# Upload results
upload_to_leaderboard(
    results=evaluation_results,
    leaderboard="global",
    submission_type="anonymous",  # or "pseudonymous", "attributed"
    display_name="ResearchBot Pro",  # optional
    metadata={
        "model_family": "gpt-4",
        "specialization": "scientific_research"
    }
)

# Query leaderboard
from praval.evaluation import get_leaderboard

rankings = get_leaderboard(
    leaderboard="reasoning",
    top_n=10,
    filters={"verification_level": "automated"}
)

for rank, entry in enumerate(rankings, 1):
    print(f"{rank}. {entry['display_name']}: {entry['score']:.3f}")
```

#### Web Interface

**URL**: `https://leaderboard.pravalagents.com`

**Features**:
- Interactive tables with sorting/filtering
- Score distribution charts
- Historical trend graphs
- Detailed result comparison
- Agent profile pages (if attributed)

### Evaluation Marketplace

#### Community Test Scenarios

**Structure**:
```
marketplace/
├── scenarios/
│   ├── contributed/
│   │   ├── medical_qa/          (by @medical_ai_lab)
│   │   ├── legal_reasoning/     (by @legal_tech_team)
│   │   └── creative_writing/    (by @ai_writers_guild)
│   └── official/
│       ├── praval_standard_v1/
│       └── praval_standard_v2/
```

**Contribution Process**:
```bash
# Submit test scenarios
praval contribute-scenarios \
  --scenarios my_scenarios/ \
  --category medical_qa \
  --description "100 clinical reasoning cases" \
  --license MIT

# Download community scenarios
praval download-scenarios medical_qa \
  --author @medical_ai_lab \
  --output evaluation/scenarios/medical/
```

#### Custom Judge Marketplace

```python
# Publish custom judge
from praval.evaluation import publish_judge

publish_judge(
    judge_class=MedicalSafetyJudge,
    name="medical_safety_judge",
    description="Evaluates medical responses for safety and accuracy",
    version="1.0.0",
    license="MIT",
    examples=[...]
)

# Install and use community judge
praval install-judge medical_safety_judge

from praval.evaluation import get_judge
judge = get_judge("medical_safety_judge")
```

### Certification System

#### Certification Levels

**1. Praval Certified**
- Passes standard benchmark (≥0.75)
- Meets basic performance criteria
- Badge: `praval_certified_v1`

**2. Praval Advanced**
- Passes advanced benchmark (≥0.85)
- Demonstrated robustness
- Badge: `praval_advanced_v1`

**3. Domain Expert**
- Passes domain-specific benchmark (≥0.90)
- Verified by domain experts
- Badge: `praval_expert_{domain}_v1`

**4. Production Ready**
- Passes all certification levels
- Demonstrated reliability under load
- Security audit passed
- Badge: `praval_production_ready_v1`

#### Certification API

```python
from praval.evaluation import certify_agent

# Run certification
certification = certify_agent(
    agent=medical_expert_agent,
    certification_type="domain_expert",
    domain="medical",
    requirements={
        "accuracy": 0.95,
        "safety_score": 1.0,
        "hallucination_rate": 0.01,
        "latency_p95": 5.0
    }
)

if certification.passed:
    print(f"🎉 Certified! Badge: {certification.badge}")
    
    # Add badge to agent metadata
    agent.metadata["certifications"] = [certification.badge]
    
    # Generate certificate
    certification.generate_certificate("certificate.pdf")
else:
    print(f"❌ Certification failed:")
    for criterion, result in certification.results.items():
        if not result.passed:
            print(f"  - {criterion}: {result.score} (required: {result.threshold})")
```

#### Badge Display

```python
# In agent code
@agent("medical_expert", responds_to=["medical_query"])
@certified(["praval_expert_medical_v1", "praval_production_ready_v1"])
def medical_expert_agent(spore):
    """
    Certified medical information agent.
    
    Certifications:
    - 🏅 Praval Expert (Medical) v1
    - ✅ Praval Production Ready v1
    """
    return expert_medical_response(spore.knowledge["query"])
```

### Research & Publications

#### Reproducibility Support

**Dataset for Research**:
```python
# Export evaluation dataset for research
from praval.evaluation import export_research_dataset

dataset = export_research_dataset(
    results=all_evaluation_results,
    anonymize=True,
    include_prompts=True,
    include_responses=False,  # Privacy
    format="json"
)

dataset.save("praval_evaluation_dataset_2024.json")
```

**Citation Format**:
```bibtex
@software{praval_evaluation_2024,
  title={Praval Evaluation Framework},
  author={Praval Contributors},
  year={2024},
  url={https://github.com/aiexplorations/praval},
  version={0.8.0}
}

@dataset{praval_benchmark_v1,
  title={Praval Standard Benchmark v1},
  author={Praval Core Team},
  year={2024},
  publisher={Praval},
  url={https://pravalagents.com/benchmarks/standard_v1}
}
```

---

## Implementation Roadmap

### Phase 1: Core Infrastructure (Weeks 1-2)

#### Week 1: Foundation

**Goals**:
- Basic decorator implementation
- Simple metric collectors
- Console reporting

**Deliverables**:
```python
# Functional by end of Week 1
@evaluate_agent(metrics=["latency", "tokens"])
def my_agent(spore):
    return result

# Console output working
```

**Tasks**:
1. Create project structure
2. Implement `@evaluate_agent` decorator
3. Build basic collectors (performance metrics)
4. Console reporter
5. Unit tests for core functionality

**Success Criteria**:
- [ ] Decorator successfully instruments agents
- [ ] Latency and token metrics collected
- [ ] Basic console report generated
- [ ] 80% test coverage on core

#### Week 2: Quality & Testing

**Goals**:
- LLM judge implementation
- Test scenario system
- JSON reporter

**Deliverables**:
```python
# Working by end of Week 2
@evaluate_agent(
    metrics=["accuracy", "relevance"],
    test_cases="test_scenarios.json"
)
def my_agent(spore):
    return result
```

**Tasks**:
1. Implement LLMJudge class
2. Create test scenario loader
3. Build JSON reporter
4. Create 10-15 example scenarios
5. Integration tests

**Success Criteria**:
- [ ] LLM judge evaluates responses
- [ ] Test scenarios loaded from JSON
- [ ] JSON report generation
- [ ] Example scenarios cover basic patterns

### Phase 2: Advanced Features (Weeks 3-4)

#### Week 3: Multi-Agent & Workflow

**Goals**:
- Workflow evaluation
- Tracing system
- HTML reporting

**Deliverables**:
```python
@evaluate_workflow(
    agents=[agent1, agent2],
    scenarios="workflow_tests.json",
    trace=True
)
def my_workflow():
    start_agents(...)
```

**Tasks**:
1. Implement `@evaluate_workflow`
2. Build tracing system
3. Workflow-specific metrics
4. HTML reporter with visualizations
5. Trace visualization

**Success Criteria**:
- [ ] Multi-agent workflows evaluated
- [ ] Execution traces captured
- [ ] Interactive HTML reports
- [ ] Workflow visualizations

#### Week 4: Benchmarks & Regression

**Goals**:
- Standard benchmark suite
- Regression testing
- Comparative analysis

**Deliverables**:
- praval_standard_v1.json (50 test cases)
- Regression testing framework
- Comparison reports

**Tasks**:
1. Create standard benchmark
2. Implement benchmark runner
3. Build regression detector
4. Comparison visualizations
5. Documentation

**Success Criteria**:
- [ ] Standard benchmark complete
- [ ] Regression testing functional
- [ ] Comparison reports clear
- [ ] Documentation comprehensive

### Phase 3: Ecosystem Features (Weeks 5-6)

#### Week 5: Community Features

**Goals**:
- Leaderboard backend
- Submission system
- Public API

**Deliverables**:
- Leaderboard web service
- Upload/download APIs
- Web interface

**Tasks**:
1. Build leaderboard backend
2. Create submission API
3. Implement web interface
4. Privacy & verification system
5. API documentation

**Success Criteria**:
- [ ] Leaderboard accepts submissions
- [ ] Web interface functional
- [ ] Privacy options working
- [ ] API documented

#### Week 6: Polish & Launch

**Goals**:
- CLI tools
- Example gallery
- Launch materials

**Deliverables**:
- `praval evaluate` CLI
- 10+ evaluation examples
- Launch blog post & docs

**Tasks**:
1. Implement CLI tools
2. Create example gallery
3. Write comprehensive docs
4. Prepare launch materials
5. Community onboarding

**Success Criteria**:
- [ ] CLI fully functional
- [ ] Examples cover common patterns
- [ ] Documentation complete
- [ ] Ready for v0.8.0 release

### Post-Launch: Iteration (Weeks 7+)

**Continuous Improvements**:
- Community feedback integration
- Additional benchmark categories
- Performance optimizations
- Plugin ecosystem growth
- Research collaborations

---

## Success Metrics

### Framework Adoption

**Metrics**:
- Monthly active evaluators
- Agents evaluated per month
- Unique users running evaluations
- GitHub stars/forks on evaluation module

**Targets** (3 months post-launch):
- 100+ monthly active evaluators
- 500+ agents evaluated
- 50+ contributors

### Quality Signal

**Metrics**:
- Evaluation results improve over time
- Fewer production issues for evaluated agents
- Community reports evaluation usefulness

**Targets**:
- 80% of developers report improved confidence
- 50% reduction in production issues for evaluated agents

### Ecosystem Growth

**Metrics**:
- Community-contributed benchmarks
- Custom metrics/judges published
- Leaderboard submissions
- Citations in research papers

**Targets**:
- 10+ community benchmarks
- 20+ custom metrics/judges
- 100+ leaderboard entries
- 5+ research citations

### Developer Experience

**Metrics**:
- Time to first evaluation
- Documentation satisfaction
- Issue resolution time
- Community engagement

**Targets**:
- <5 minutes to first evaluation
- 90%+ documentation satisfaction
- <24 hour issue response time
- Active community discussions

---

## Appendices

### Appendix A: Comparison with Other Frameworks

| Feature | Praval Eval | LangSmith | PromptFoo | Ragas | OpenAI Evals |
|---------|-------------|-----------|-----------|-------|--------------|
| **Integration** | Native decorators | Separate platform | CLI-based | Library | Repository-based |
| **Agent-Specific** | ✅ Multi-agent focus | ❌ Chain-focused | ❌ Prompt-focused | ❌ RAG-focused | ❌ Generic |
| **Workflow Eval** | ✅ Built-in | ⚠️ Limited | ❌ No | ❌ No | ❌ No |
| **LLM-as-Judge** | ✅ Yes | ✅ Yes | ✅ Yes | ⚠️ Limited | ⚠️ Basic |
| **Community** | ✅ Leaderboard | ✅ Cloud | ❌ No | ❌ No | ✅ GitHub |
| **Cost** | Free | Paid | Free | Free | Free |
| **Self-Hosted** | ✅ Yes | ⚠️ Limited | ✅ Yes | ✅ Yes | ✅ Yes |

**Unique Value Propositions**:
1. **Native Praval Integration**: Zero-friction evaluation for Praval agents
2. **Multi-Agent Focus**: Only framework designed for agent collaboration
3. **Decorator-Based**: Matches Praval's elegant API style
4. **Community Ecosystem**: Shared benchmarks and knowledge
5. **Open Standards**: Interoperable with other tools

### Appendix B: Technical Architecture Details

#### Instrumentation Strategy

**Non-Invasive Approach**:
```python
# Original agent code unchanged
@agent("researcher", responds_to=["query"])
def research_agent(spore):
    return result

# Evaluation adds wrapper
@evaluate_agent(...)
@agent("researcher", responds_to=["query"])
def research_agent(spore):
    return result

# No changes to agent logic required
```

**Instrumentation Points**:
1. Function entry (timing start, context capture)
2. LLM calls (token counting, cost tracking)
3. Reef messages (communication patterns)
4. Memory accesses (retrieval metrics)
5. Tool calls (external API usage)
6. Function exit (timing end, result capture)
7. Exception handling (error metrics)

#### Data Flow

```
┌───────────────┐
│ Agent Call    │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ @evaluate     │◄─── Intercepts execution
│ Decorator     │
└───────┬───────┘
        │
        ├─────────────────────────────┐
        │                             │
        ▼                             ▼
┌───────────────┐            ┌───────────────┐
│ Metric        │            │ Original      │
│ Collectors    │            │ Agent Logic   │
│ (async)       │            │               │
└───────┬───────┘            └───────┬───────┘
        │                            │
        │                            ▼
        │                    ┌───────────────┐
        │                    │ Result        │
        │                    └───────┬───────┘
        │                            │
        └────────────┬───────────────┘
                     │
                     ▼
             ┌───────────────┐
             │ Evaluation    │
             │ Engine        │
             └───────┬───────┘
                     │
                     ▼
             ┌───────────────┐
             │ Reporters     │
             └───────────────┘
```

#### Storage Schema

**Local SQLite Database**:
```sql
-- evaluations table
CREATE TABLE evaluations (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    overall_score REAL,
    passed BOOLEAN,
    metadata JSON
);

-- metrics table
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id TEXT,
    metric_name TEXT,
    metric_value REAL,
    metadata JSON,
    FOREIGN KEY(evaluation_id) REFERENCES evaluations(id)
);

-- test_cases table
CREATE TABLE test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id TEXT,
    test_case_id TEXT,
    passed BOOLEAN,
    score REAL,
    input JSON,
    output JSON,
    expected JSON,
    FOREIGN KEY(evaluation_id) REFERENCES evaluations(id)
);
```

#### Performance Considerations

**Async Collection**:
- Metrics collected asynchronously to minimize overhead
- Background thread pool for judge evaluations
- Results buffered and batch-written

**Caching**:
- LLM judge responses cached (deterministic prompts)
- Test scenario parsing cached
- Benchmark loading cached

**Optimization Flags**:
```python
@evaluate_agent(
    metrics=["accuracy"],
    optimization="fast",  # Reduces judge calls, samples test cases
    cache_judges=True,
    batch_size=10
)
```

### Appendix C: Security & Privacy

#### Data Privacy

**Principles**:
1. **Local-First**: All evaluation data stored locally by default
2. **Opt-In Sharing**: Must explicitly choose to share results
3. **Anonymization**: Remove identifying information before sharing
4. **Transparency**: Clear data usage policies

**Implementation**:
```python
# Data stays local
results = evaluate_agent(agent, store_local=True)

# Explicit sharing with anonymization
results.share(
    leaderboard="global",
    anonymize=True,  # Removes: agent names, prompts, responses
    metadata_only=True  # Only scores, no content
)
```

#### Security Considerations

**LLM Judge Security**:
- Prompt injection prevention
- Output validation
- Rate limiting
- API key protection

**Benchmark Integrity**:
- Cryptographic signatures for official benchmarks
- Version control and audit trails
- Tampering detection

### Appendix D: Future Enhancements

**Planned Features** (Post-v1.0):

1. **Real-Time Evaluation**
   - Live monitoring during agent execution
   - Alert on quality degradation
   - Automatic rollback triggers

2. **Adversarial Testing**
   - Automatic generation of adversarial inputs
   - Robustness stress testing
   - Security vulnerability scanning

3. **Multi-Modal Evaluation**
   - Image generation quality metrics
   - Audio quality assessment
   - Video analysis

4. **Cost Optimization**
   - Automatic judge model selection
   - Batch evaluation scheduling
   - Cache optimization recommendations

5. **Explainability**
   - Detailed reasoning traces
   - Counterfactual analysis
   - Feature attribution

6. **Integration Ecosystem**
   - Weights & Biases integration
   - MLflow tracking
   - TensorBoard visualization
   - Slack/Discord notifications

---

## Conclusion

The Praval Evaluation Framework represents a comprehensive approach to agent quality assessment that:

1. **Maintains Simplicity**: Decorator-based API matches Praval's elegant design
2. **Scales Complexity**: From single agents to complex multi-agent workflows
3. **Enables Community**: Shared standards and benchmarks foster ecosystem growth
4. **Provides Confidence**: Objective metrics give developers deployment assurance
5. **Supports Research**: Open standards and reproducibility enable academic work

By implementing this framework, Praval will:
- **Differentiate** from other frameworks with native evaluation support
- **Build Trust** through transparent quality metrics
- **Grow Community** via shared benchmarks and leaderboards
- **Enable Discovery** of high-quality agents
- **Support Adoption** with clear quality signals

This specification provides a complete roadmap for building an evaluation system that becomes a core value proposition of the Praval ecosystem.

---

**Next Steps**:
1. Review and refine this specification
2. Begin Phase 1 implementation
3. Create example use cases
4. Engage community for feedback
5. Launch with v0.8.0 release

**Questions & Feedback**: [GitHub Discussions](https://github.com/aiexplorations/praval/discussions)