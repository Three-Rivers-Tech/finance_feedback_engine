#!/usr/bin/env python3
"""
Demo script for the Sequential Thinking MCP Server.

This script demonstrates the sequential_thinking tool's capabilities
for breaking down complex problems into manageable steps with dynamic
revision and branching capabilities.
"""

import asyncio
import json
from typing import Any, Dict


async def demonstrate_sequential_thinking():
    """
    Demonstrate the sequential_thinking tool with a complex problem.

    This example shows:
    1. Breaking down a problem into steps
    2. Revising thoughts as understanding deepens
    3. Dynamic adjustment of total thoughts needed
    4. Branching into alternative reasoning paths
    """

    print("=" * 80)
    print("Sequential Thinking MCP Server Demonstration")
    print("=" * 80)
    print()

    # Problem: Design a scalable microservices architecture
    problem = """
    Design a scalable microservices architecture for a financial trading platform
    that needs to handle real-time market data, execute trades, manage portfolios,
    and provide analytics.
    """

    print(f"Problem to solve:\n{problem}\n")
    print("-" * 80)
    print()

    # Simulated sequential thinking process
    thoughts = [
        {
            "thought_number": 1,
            "total_thoughts": 5,
            "thought": "First, I need to identify the core services required: Market Data Service, Trading Execution Service, Portfolio Management Service, and Analytics Service.",
            "next_thought_needed": True,
            "is_revision": False,
        },
        {
            "thought_number": 2,
            "total_thoughts": 5,
            "thought": "Each service should be independently deployable and scalable. Market Data Service needs to handle high-frequency updates, so it should use a message queue (e.g., Kafka) for real-time streaming.",
            "next_thought_needed": True,
            "is_revision": False,
        },
        {
            "thought_number": 3,
            "total_thoughts": 6,
            "thought": "Wait, I should reconsider the architecture. We also need an API Gateway for routing and authentication, and a separate User Service for account management.",
            "next_thought_needed": True,
            "is_revision": True,
            "revises_thought": 1,
            "needs_more_thoughts": True,
        },
        {
            "thought_number": 4,
            "total_thoughts": 6,
            "thought": "For data persistence: Market Data Service uses time-series DB (InfluxDB/TimescaleDB), Portfolio Service uses PostgreSQL for transactional data, Analytics Service uses a data warehouse (e.g., Snowflake).",
            "next_thought_needed": True,
            "is_revision": False,
        },
        {
            "thought_number": 5,
            "total_thoughts": 7,
            "thought": "Let me explore an alternative approach for the Trading Execution Service. Branch A: Use synchronous REST APIs for simplicity. Branch B: Use event-driven architecture with CQRS pattern for better scalability.",
            "next_thought_needed": True,
            "is_revision": False,
            "branch_from_thought": 2,
            "branch_id": "execution-architecture",
            "needs_more_thoughts": True,
        },
        {
            "thought_number": 6,
            "total_thoughts": 7,
            "thought": "Going with Branch B (event-driven with CQRS): Trading commands are handled asynchronously, with separate read/write models. This provides better audit trails and allows replay of trading events.",
            "next_thought_needed": True,
            "is_revision": False,
        },
        {
            "thought_number": 7,
            "total_thoughts": 7,
            "thought": "Final architecture summary: 6 core microservices (API Gateway, User, Market Data, Trading, Portfolio, Analytics), event-driven communication via Kafka, polyglot persistence, containerized with Kubernetes for orchestration.",
            "next_thought_needed": False,
            "is_revision": False,
        },
    ]

    # Simulate the sequential thinking process
    for thought_data in thoughts:
        print(
            f"Thought {thought_data['thought_number']}/{thought_data['total_thoughts']}:"
        )

        if thought_data.get("is_revision"):
            print(f"  [REVISION of thought {thought_data.get('revises_thought')}]")

        if thought_data.get("branch_from_thought"):
            print(
                f"  [BRANCH from thought {thought_data.get('branch_from_thought')}: {thought_data.get('branch_id')}]"
            )

        print(f"  {thought_data['thought']}")

        if thought_data.get("needs_more_thoughts"):
            print(
                f"  [Adjusting total thoughts needed from {thought_data['total_thoughts']-1} to {thought_data['total_thoughts']}]"
            )

        print()

        # Small delay to simulate thinking process
        await asyncio.sleep(0.5)

    print("-" * 80)
    print("\nSequential thinking process complete!")
    print("\nKey insights from the process:")
    print("1. Started with 5 planned thoughts, expanded to 7 as complexity emerged")
    print("2. Revised initial architecture to include API Gateway and User Service")
    print("3. Explored alternative approaches for Trading Execution Service")
    print("4. Chose event-driven architecture with CQRS for better scalability")
    print("\n" + "=" * 80)


async def demonstrate_error_handling():
    """
    Demonstrate error handling in sequential thinking.
    """
    print("\n" + "=" * 80)
    print("Error Handling Demonstration")
    print("=" * 80)
    print()

    # Example of handling invalid thought numbers
    invalid_cases = [
        {"thought_number": 0, "error": "Thought number must be positive"},
        {
            "thought_number": 5,
            "total_thoughts": 3,
            "error": "Thought number exceeds total",
        },
        {
            "is_revision": True,
            "revises_thought": None,
            "error": "Revision missing target",
        },
    ]

    for case in invalid_cases:
        print(f"Invalid case: {case}")
        print(f"Expected error: {case.get('error')}")
        print()


async def main():
    """Main demonstration function."""
    await demonstrate_sequential_thinking()
    await demonstrate_error_handling()


if __name__ == "__main__":
    asyncio.run(main())
