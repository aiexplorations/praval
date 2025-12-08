#!/usr/bin/env python3
"""
Agentic Calculator - A CLI Mathematical Assistant

An intelligent calculator agent built with Praval's new tool system.
Tools are defined using the @tool decorator and automatically registered
with the calculator agent. The agent performs various mathematical operations
through natural language commands using registered tools for precise calculations.

Usage:
    python examples/calculator.py
    
Examples:
    - "What is 15 + 27?"
    - "Calculate the square root of 144"
    - "What's 5 factorial?"
    - "Convert 100 degrees Celsius to Fahrenheit"
    - "Find the area of a circle with radius 5"
"""

import logging
import math
import sys
import os

# Add the src directory to the path to import praval
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from praval import agent, chat, tool, start_agents, get_reef, get_tool_registry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('calculator.log')
    ]
)
logger = logging.getLogger(__name__)


# ==========================================
# MATHEMATICAL TOOLS DEFINITION
# ==========================================
# Tools are defined first and automatically registered with the calculator agent

# Basic Arithmetic Tools
@tool("add", owned_by="calculator", category="arithmetic", description="Add two numbers together")
def add(x: float, y: float) -> float:
    """Add two numbers together."""
    result = x + y
    logger.info(f"Addition: {x} + {y} = {result}")
    return result


@tool("subtract", owned_by="calculator", category="arithmetic", description="Subtract two numbers")
def subtract(x: float, y: float) -> float:
    """Subtract the second number from the first number."""
    result = x - y
    logger.info(f"Subtraction: {x} - {y} = {result}")
    return result


@tool("multiply", owned_by="calculator", category="arithmetic", description="Multiply two numbers")
def multiply(x: float, y: float) -> float:
    """Multiply two numbers together."""
    result = x * y
    logger.info(f"Multiplication: {x} × {y} = {result}")
    return result


@tool("divide", owned_by="calculator", category="arithmetic", description="Divide two numbers")
def divide(x: float, y: float) -> float:
    """Divide the first number by the second number."""
    if y == 0:
        logger.error("Division by zero attempted")
        raise ValueError("Cannot divide by zero")
    result = x / y
    logger.info(f"Division: {x} ÷ {y} = {result}")
    return result


# Advanced Mathematical Functions
@tool("power", owned_by="calculator", category="advanced", description="Raise number to a power")
def power(base: float, exponent: float) -> float:
    """Raise a number to a power (base^exponent)."""
    result = math.pow(base, exponent)
    logger.info(f"Power: {base}^{exponent} = {result}")
    return result


@tool("square_root", owned_by="calculator", category="advanced", description="Calculate square root")
def square_root(x: float) -> float:
    """Calculate the square root of a number."""
    if x < 0:
        logger.error(f"Square root of negative number attempted: {x}")
        raise ValueError("Cannot calculate square root of negative number")
    result = math.sqrt(x)
    logger.info(f"Square root: √{x} = {result}")
    return result


@tool("logarithm", owned_by="calculator", category="advanced", description="Calculate logarithm")
def logarithm(x: float, base: float = math.e) -> float:
    """Calculate logarithm of x with given base (default: natural log)."""
    if x <= 0:
        logger.error(f"Logarithm of non-positive number attempted: {x}")
        raise ValueError("Cannot calculate logarithm of non-positive number")
    if base == math.e:
        result = math.log(x)
        logger.info(f"Natural log: ln({x}) = {result}")
    else:
        result = math.log(x, base)
        logger.info(f"Logarithm: log_{base}({x}) = {result}")
    return result


@tool("factorial", owned_by="calculator", category="advanced", description="Calculate factorial")
def factorial(n: int) -> int:
    """Calculate the factorial of a non-negative integer."""
    if n < 0:
        logger.error(f"Factorial of negative number attempted: {n}")
        raise ValueError("Cannot calculate factorial of negative number")
    if n > 170:  # Prevent overflow
        logger.error(f"Factorial too large: {n}")
        raise ValueError("Factorial too large (maximum 170)")
    result = math.factorial(n)
    logger.info(f"Factorial: {n}! = {result}")
    return result


# Trigonometric Functions
@tool("sine", owned_by="calculator", category="trigonometry", description="Calculate sine")
def sine(angle_degrees: float) -> float:
    """Calculate sine of an angle in degrees."""
    angle_radians = math.radians(angle_degrees)
    result = math.sin(angle_radians)
    logger.info(f"Sine: sin({angle_degrees}°) = {result}")
    return result


@tool("cosine", owned_by="calculator", category="trigonometry", description="Calculate cosine")
def cosine(angle_degrees: float) -> float:
    """Calculate cosine of an angle in degrees."""
    angle_radians = math.radians(angle_degrees)
    result = math.cos(angle_radians)
    logger.info(f"Cosine: cos({angle_degrees}°) = {result}")
    return result


@tool("tangent", owned_by="calculator", category="trigonometry", description="Calculate tangent")
def tangent(angle_degrees: float) -> float:
    """Calculate tangent of an angle in degrees."""
    angle_radians = math.radians(angle_degrees)
    result = math.tan(angle_radians)
    logger.info(f"Tangent: tan({angle_degrees}°) = {result}")
    return result


# Unit Conversion Tools
@tool("celsius_to_fahrenheit", owned_by="calculator", category="conversion", description="Convert Celsius to Fahrenheit")
def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert temperature from Celsius to Fahrenheit."""
    fahrenheit = (celsius * 9/5) + 32
    logger.info(f"Temperature conversion: {celsius}°C = {fahrenheit}°F")
    return fahrenheit


@tool("fahrenheit_to_celsius", owned_by="calculator", category="conversion", description="Convert Fahrenheit to Celsius")
def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert temperature from Fahrenheit to Celsius."""
    celsius = (fahrenheit - 32) * 5/9
    logger.info(f"Temperature conversion: {fahrenheit}°F = {celsius}°C")
    return celsius


@tool("meters_to_feet", owned_by="calculator", category="conversion", description="Convert meters to feet")
def meters_to_feet(meters: float) -> float:
    """Convert distance from meters to feet."""
    feet = meters * 3.28084
    logger.info(f"Distance conversion: {meters}m = {feet}ft")
    return feet


@tool("feet_to_meters", owned_by="calculator", category="conversion", description="Convert feet to meters")
def feet_to_meters(feet: float) -> float:
    """Convert distance from feet to meters."""
    meters = feet / 3.28084
    logger.info(f"Distance conversion: {feet}ft = {meters}m")
    return meters


# Geometric Calculation Tools
@tool("circle_area", owned_by="calculator", category="geometry", description="Calculate circle area")
def circle_area(radius: float) -> float:
    """Calculate the area of a circle given its radius."""
    if radius < 0:
        logger.error(f"Negative radius for circle area: {radius}")
        raise ValueError("Radius cannot be negative")
    area = math.pi * radius * radius
    logger.info(f"Circle area: π × {radius}² = {area}")
    return area


@tool("rectangle_area", owned_by="calculator", category="geometry", description="Calculate rectangle area")
def rectangle_area(length: float, width: float) -> float:
    """Calculate the area of a rectangle given length and width."""
    if length < 0 or width < 0:
        logger.error(f"Negative dimensions for rectangle: {length} × {width}")
        raise ValueError("Dimensions cannot be negative")
    area = length * width
    logger.info(f"Rectangle area: {length} × {width} = {area}")
    return area


@tool("sphere_volume", owned_by="calculator", category="geometry", description="Calculate sphere volume")
def sphere_volume(radius: float) -> float:
    """Calculate the volume of a sphere given its radius."""
    if radius < 0:
        logger.error(f"Negative radius for sphere volume: {radius}")
        raise ValueError("Radius cannot be negative")
    volume = (4/3) * math.pi * radius**3
    logger.info(f"Sphere volume: (4/3)π × {radius}³ = {volume}")
    return volume


# Statistical Calculation Tools
@tool("percentage", owned_by="calculator", category="statistics", description="Calculate percentage")
def percentage(part: float, whole: float) -> float:
    """Calculate what percentage the part is of the whole."""
    if whole == 0:
        logger.error("Percentage calculation with zero denominator")
        raise ValueError("Cannot calculate percentage with zero whole")
    percent = (part / whole) * 100
    logger.info(f"Percentage: ({part}/{whole}) × 100 = {percent}%")
    return percent


@tool("percentage_of", owned_by="calculator", category="statistics", description="Calculate percentage of number")
def percentage_of(percent: float, number: float) -> float:
    """Calculate what amount is the given percentage of a number."""
    result = (percent / 100) * number
    logger.info(f"Percentage calculation: {percent}% of {number} = {result}")
    return result


# ==========================================
# CALCULATOR AGENT DEFINITION
# ==========================================

# Global variable to store the last response for CLI display
_last_response = {"result": None}


@agent(
    "calculator",
    responds_to=["calculator_query"],
    system_message="""You are a precise mathematical assistant. You have access to various
    mathematical tools to perform calculations accurately. Always use the appropriate tool
    for calculations rather than estimating. Provide clear, step-by-step explanations when
    helpful, and format your responses in a friendly, conversational manner.""",
    memory=True
)
def calculator_agent(spore):
    """
    Intelligent calculator agent that processes mathematical queries.

    The agent automatically selects and uses appropriate mathematical tools
    based on the user's natural language input, providing accurate calculations
    with conversational responses.

    All tools are automatically registered and available through the
    Praval tool system.
    """
    query = spore.knowledge.get("query", "")
    logger.info(f"Processing mathematical query: {query}")

    # Use chat() inside the agent context - this is the proper pattern
    response = chat(query)

    # Store response for CLI to display
    _last_response["result"] = response

    return {"status": "complete", "query": query, "response": response}


# ==========================================
# CLI INTERFACE FUNCTIONS
# ==========================================

def show_help():
    """Display available mathematical operations and examples."""
    print()
    print("📚 Available Mathematical Operations:")
    print("=" * 40)

    # Get tools by category from the registry
    registry = get_tool_registry()
    categories = {}
    
    for tool_obj in registry.get_tools_for_agent("calculator"):
        category = tool_obj.metadata.category
        if category not in categories:
            categories[category] = []
        categories[category].append(tool_obj)
    
    # Display tools by category
    category_icons = {
        "arithmetic": "🔢",
        "advanced": "📐", 
        "trigonometry": "📊",
        "conversion": "🌡️",
        "geometry": "📏",
        "statistics": "📈"
    }
    
    for category, tools in categories.items():
        icon = category_icons.get(category, "🔧")
        print(f"{icon} {category.title()}:")
        for tool_obj in tools:
            print(f"  • {tool_obj.metadata.description}")
        print()
    
    print("💡 Just ask in natural language!")
    print("=" * 40)
    print()


def run_calculator_cli():
    """
    Run the interactive command-line interface for the calculator.
    
    Provides a continuous loop for mathematical conversations with
    the agent, including help commands and graceful exit handling.
    """
    print("🧮 Agentic Calculator - Your Mathematical Assistant")
    print("=" * 55)
    print("Ask me any mathematical question in natural language!")
    print()
    print("Examples:")
    print("  • What is 25 + 17?")
    print("  • Calculate the square root of 144")
    print("  • What's 5 factorial?")
    print("  • Convert 100°C to Fahrenheit")
    print("  • Find the area of a circle with radius 7")
    print("  • What percentage is 25 of 200?")
    print()
    print("Commands:")
    print("  • 'help' - Show available operations")
    print("  • 'quit' or 'exit' - Exit the calculator")
    print("=" * 55)
    print()
    
    # Display initial tool count using the tool registry
    registry = get_tool_registry()
    tool_count = len(registry.get_tools_for_agent("calculator"))
    print(f"📊 Calculator agent initialized with {tool_count} mathematical tools")
    print()

    while True:
        try:
            # Get user input
            user_input = input("🤖 Ask me: ").strip()

            if not user_input:
                continue

            # Handle special commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Thanks for using Agentic Calculator!")
                logger.info("Calculator session ended by user")
                break

            if user_input.lower() in ['help', 'h']:
                show_help()
                continue

            # Process mathematical query using the agent
            print("🔄 Calculating...")
            logger.info(f"User input: {user_input}")

            try:
                # Reset the response holder
                _last_response["result"] = None

                # Use start_agents() to trigger the agent with the query
                # This is the proper pattern for @agent decorated functions
                start_agents(
                    calculator_agent,
                    initial_data={
                        "type": "calculator_query",
                        "query": user_input
                    }
                )

                # Wait for the agent to complete processing
                get_reef().wait_for_completion()

                # Display the response
                if _last_response["result"]:
                    print(f"📊 {_last_response['result']}")
                    logger.info("Agent response generated successfully")
                else:
                    print("📊 Query processed.")
                print()

            except Exception as e:
                print(f"❌ Calculation error: {str(e)}")
                logger.error(f"Error processing query: {str(e)}")
                print()

        except KeyboardInterrupt:
            print("\n👋 Thanks for using Agentic Calculator!")
            logger.info("Calculator session interrupted by user")
            break
        except Exception as e:
            print(f"❌ An error occurred: {str(e)}")
            logger.error(f"Unexpected error in CLI: {str(e)}")


def main():
    """Main entry point for the agentic calculator."""
    try:
        logger.info("Starting Agentic Calculator with new tool system...")

        # Display summary of registered tools
        registry = get_tool_registry()
        all_tools = registry.list_all_tools()
        calculator_tools = registry.get_tools_for_agent("calculator")
        
        print(f"🔧 Tool Registry Summary:")
        print(f"   Total tools registered: {len(all_tools)}")
        print(f"   Calculator tools: {len(calculator_tools)}")
        
        # Show tools by category
        categories = {}
        for tool_obj in calculator_tools:
            category = tool_obj.metadata.category
            categories[category] = categories.get(category, 0) + 1
        
        print("   Tools by category:")
        for category, count in categories.items():
            print(f"     - {category}: {count}")
        print()
        
        run_calculator_cli()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Failed to start calculator: {str(e)}")
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
